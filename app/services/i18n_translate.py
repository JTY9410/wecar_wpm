"""글로벌 다국어 번역 + 로컬 캐시 (PRD §6.3).

- 고정 UI 문구는 app/i18n/{ko,en,ja}.json 에서 직접 로드한다 (사람이 검수한 번역).
- 차명·낙찰 사고내역 등 자유 텍스트는 두 엔진을 조합해 번역하고 TranslationCache 에 캐시한다.
  1) Google Cloud Translation API (관리자 LLM 설정에서 키 등록 시) — 넓은 커버리지의 1차 번역.
  2) Gemini(llm_hub.GeminiProvider) — Google 번역 결과를 용어집/과거 캐시를 참고해 다듬는다(윤문).
     Google 키가 없으면 Gemini가 직접 번역, 둘 다 없으면 원문 그대로 반환한다(그레이스풀 패스스루).
- 같은 용어가 항상 같은 번역이 되도록, 고정 UI 사전(ko→lang)을 용어집으로 프롬프트에
  포함하고, 과거 캐시된 번역도 few-shot 예시로 재사용해 톤을 일관되게 유지한다.
"""
import hashlib
import json
import logging
import os

from config import Config
from app.extensions import db
from app.models import TranslationCache
from app.services import google_translate

logger = logging.getLogger(__name__)

_I18N_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "i18n")
_LANG_NAMES = {"en": "English", "ja": "Japanese"}


def load_pack(lang):
    if lang not in Config.SUPPORTED_LANGS:
        lang = "ko"
    path = os.path.join(_I18N_DIR, f"{lang}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _static_lookup(text, lang):
    """정적 UI 사전에 이미 있는 값이면 검수된 번역을 그대로 재사용."""
    ko_pack = load_pack("ko")
    for key, ko_value in ko_pack.items():
        if ko_value == text:
            target = load_pack(lang).get(key)
            if target:
                return target
    return None


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _glossary_pairs(lang, limit=15):
    """정적 UI 사전에서 용어집 예시 추출 — 도메인 용어 일관성 유지."""
    ko_pack = load_pack("ko")
    target_pack = load_pack(lang)
    pairs = [
        (ko_pack[k], target_pack[k])
        for k in ko_pack
        if k in target_pack and ko_pack[k] and ko_pack[k] != target_pack[k]
    ]
    return pairs[:limit]


def _cache_examples(lang, limit=5):
    """과거 성공 번역 캐시를 few-shot 예시로 재사용 — 톤 일관성 학습 효과."""
    rows = (
        TranslationCache.query.filter(
            TranslationCache.lang == lang,
            TranslationCache.source_text != TranslationCache.translated_text,
        )
        .order_by(TranslationCache.id.desc())
        .limit(limit)
        .all()
    )
    return [(r.source_text, r.translated_text) for r in rows]


def _build_prompt(text, lang, draft=None):
    target = _LANG_NAMES[lang]
    examples = _glossary_pairs(lang) + _cache_examples(lang)
    example_lines = "\n".join(f"- {ko} → {tr}" for ko, tr in examples)
    if draft:
        task = (
            f"A Korean used-car wholesale-auction text was machine-translated into {target} below. "
            f"Polish it into natural, concise {target} suitable for a UI or market report, "
            f"fixing anything left untranslated or awkward. "
            f"Keep numbers, model names, and proper nouns unchanged. "
            f"Return ONLY the final text, with no quotes or extra notes.\n\n"
        )
        body = f"Korean source: {text}\n{target} draft: {draft}"
    else:
        task = (
            f"Translate the following Korean used-car wholesale-auction text into "
            f"natural, concise {target} suitable for a UI or market report. "
            f"Keep numbers, model names, and proper nouns unchanged. "
            f"Return ONLY the translation, with no quotes or extra notes.\n\n"
        )
        body = f"Text: {text}"
    example_block = f"Reference terminology (Korean → {target}):\n{example_lines}\n\n" if example_lines else ""
    return task + example_block + body


def _call_gemini(text, lang, draft=None):
    from app.services.llm_hub import GeminiProvider, LLMError, resolve_api_key

    if not resolve_api_key("gemini"):
        return None
    try:
        result = GeminiProvider().generate(_build_prompt(text, lang, draft))
        return (result or "").strip() or None
    except LLMError as exc:
        logger.warning("Gemini translate failed: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Gemini translate failed: %s", exc)
        return None


def _call_provider(text, lang):
    """Google Translate로 1차 초벌 번역 후 Gemini로 다듬는다. 둘 다 없으면 원문 패스스루."""
    draft = google_translate.translate_text(text, lang)
    if draft:
        polished = _call_gemini(text, lang, draft=draft)
        return polished or draft
    direct = _call_gemini(text, lang)
    return direct or text


def translate(text, lang):
    """Translate free-form text with local cache. Falls back to source text."""
    if not text or lang == "ko" or lang not in _LANG_NAMES:
        return text
    if text in load_pack(lang).values():
        # Already-localized UI string (e.g. t('unknown')) piped through |tr —
        # don't re-translate it as if it were Korean source text.
        return text
    static = _static_lookup(text, lang)
    if static:
        return static
    h = _hash(text)
    row = TranslationCache.query.filter_by(source_hash=h, lang=lang).first()
    if row:
        return row.translated_text

    translated = _call_provider(text, lang)
    if translated == text:
        # Provider unavailable/failed — passthrough. Don't cache it, so a
        # later successful translation isn't permanently masked.
        return translated
    try:
        db.session.add(TranslationCache(source_hash=h, source_text=text, lang=lang,
                                        translated_text=translated))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning("Translation cache write failed: %s", exc)
    return translated
