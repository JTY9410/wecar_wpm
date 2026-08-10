"""글로벌 다국어 번역 + 로컬 캐시 + 자체 학습 (PRD §6.3).

파이프라인:
  1) UI 사전 / 정적 차량 용어집 / LearnedGlossary
  2) TranslationCache (hit 시 hit_count++, 임계치면 용어집 승격)
  3) Google Cloud Translation 초벌 → Gemini 윤문
  4) en/ja 결과에 Hangul이 남으면 캐시·승격하지 않음
  5) hit_count ≥ PROMOTE_THRESHOLD 또는 reviewed → LearnedGlossary 승격
"""
import hashlib
import json
import logging
import os
import re

from config import Config
from app.extensions import db
from app.models import LearnedGlossary, TranslationCache
from app.services import google_translate

logger = logging.getLogger(__name__)

_I18N_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "i18n")
_LANG_NAMES = {"en": "English", "ja": "Japanese"}
_vehicle_glossary_cache = {}
_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")
PROMOTE_THRESHOLD = 3


def load_pack(lang):
    if lang not in Config.SUPPORTED_LANGS:
        lang = "ko"
    path = os.path.join(_I18N_DIR, f"{lang}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_vehicle_glossary(lang):
    if lang not in _LANG_NAMES:
        return {}
    if lang in _vehicle_glossary_cache:
        return _vehicle_glossary_cache[lang]
    path = os.path.join(_I18N_DIR, f"vehicle_{lang}.json")
    if not os.path.exists(path):
        _vehicle_glossary_cache[lang] = {}
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    _vehicle_glossary_cache[lang] = data
    return data


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _contains_hangul(text):
    return bool(text and _HANGUL_RE.search(text))


# Gemini가 UI 섹션 덤프를 반환한 사례 (【車両検索】 등) — 짧은 라벨 번역에 섞이면 안 됨
_BAD_MARKERS = (
    "【",
    "】",
    "Reference terminology",
    "Korean source:",
    "Polish it into",
)


def _is_quality_ok(text, lang, source=None):
    """en/ja 번역 품질 가드. Hangul 잔존·개행 폭발·UI 덤프·과도한 길이 거부."""
    if not text or lang not in _LANG_NAMES:
        return False
    if _contains_hangul(text):
        return False
    if any(m in text for m in _BAD_MARKERS):
        return False
    src = source or ""
    if ("\n" in text or "\r" in text) and "\n" not in src and "\r" not in src:
        return False
    if src:
        if len(text) > max(120, len(src) * 5):
            return False
    elif len(text) > 300:
        return False
    return True


def _learned_lookup(text, lang):
    row = db.session.execute(db.select(LearnedGlossary).where(LearnedGlossary.source_hash == _hash(text), LearnedGlossary.lang == lang)).scalar_one_or_none()
    if not row:
        return None
    if _is_quality_ok(row.translated_text, lang, text):
        return row.translated_text
    try:
        db.session.delete(row)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return None


def _static_lookup(text, lang):
    vehicle = load_vehicle_glossary(lang).get(text)
    if vehicle:
        return vehicle
    learned = _learned_lookup(text, lang)
    if learned:
        return learned
    ko_pack = load_pack("ko")
    for key, ko_value in ko_pack.items():
        if ko_value == text:
            target = load_pack(lang).get(key)
            if target:
                return target
    glossary = load_vehicle_glossary(lang)
    if glossary and any(token in text for token in glossary):
        out = text
        for src, dst in sorted(glossary.items(), key=lambda kv: len(kv[0]), reverse=True):
            if src and src in out:
                out = out.replace(src, dst)
        if out != text and _is_quality_ok(out, lang, text):
            return out
    return None


def _glossary_pairs(lang, limit=20):
    pairs = list(load_vehicle_glossary(lang).items())[:8]
    learned_rows = db.session.execute(
        db.select(LearnedGlossary)
        .where(LearnedGlossary.lang == lang)
        .order_by(LearnedGlossary.updated_at.desc())
        .limit(16)
    ).scalars().all()
    for r in learned_rows:
        if _is_quality_ok(r.translated_text, lang, r.source_text):
            pairs.append((r.source_text, r.translated_text))
        if len(pairs) >= limit:
            return pairs[:limit]
    ko_pack = load_pack("ko")
    target_pack = load_pack(lang)
    for k in ko_pack:
        if k in target_pack and ko_pack[k] and ko_pack[k] != target_pack[k]:
            pairs.append((ko_pack[k], target_pack[k]))
        if len(pairs) >= limit:
            break
    return pairs[:limit]


def _cache_examples(lang, limit=8):
    rows = db.session.execute(
        db.select(TranslationCache)
        .where(
            TranslationCache.lang == lang,
            TranslationCache.source_text != TranslationCache.translated_text,
        )
        .order_by(
            TranslationCache.reviewed.desc(),
            TranslationCache.hit_count.desc(),
            TranslationCache.id.desc(),
        )
        .limit(limit * 3)
    ).scalars().all()
    return [
        (r.source_text, r.translated_text)
        for r in rows
        if _is_quality_ok(r.translated_text, lang, r.source_text)
    ][:limit]


def _build_prompt(text, lang, draft=None):
    target = _LANG_NAMES[lang]
    examples = _glossary_pairs(lang) + _cache_examples(lang)
    example_lines = "\n".join(f"- {ko} → {tr}" for ko, tr in examples)
    if draft:
        task = (
            f"A Korean used-car wholesale-auction text was machine-translated into {target} below. "
            f"Polish it into natural, concise {target} suitable for a UI or market report. "
            f"Manufacturer, model, trim/grade, and detail names MUST be translated into common "
            f"{target} equivalents (e.g. 현대→Hyundai/ヒュンダイ, 그랜저→Grandeur/グレンジャー). "
            f"Do not leave Korean Hangul in the result when a natural {target} form exists. "
            f"Keep pure numbers and Latin alphanumeric codes as-is. "
            f"Return ONLY the final text, with no quotes or extra notes.\n\n"
        )
        body = f"Korean source: {text}\n{target} draft: {draft}"
    else:
        task = (
            f"Translate the following Korean used-car wholesale-auction text into "
            f"natural, concise {target} suitable for a UI or market report. "
            f"Manufacturer, model, trim/grade, and detail names MUST be translated into common "
            f"{target} equivalents (e.g. 현대→Hyundai/ヒュンダイ, 그랜저→Grandeur/グレンジャー). "
            f"Do not leave Korean Hangul in the result when a natural {target} form exists. "
            f"Keep pure numbers and Latin alphanumeric codes as-is. "
            f"Return ONLY the translation, with no quotes or extra notes.\n\n"
        )
        body = f"Text: {text}"
    example_block = (
        f"Reference terminology (Korean → {target}):\n{example_lines}\n\n" if example_lines else ""
    )
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


def _should_polish(text, polish):
    """짧은 제조사/모델명은 Google 초벌만으로 충분 — Gemini 동기 호출은 워커 타임아웃 유발."""
    if polish is False:
        return False
    if polish is True:
        return True
    # auto: 긴 서술문만 Gemini 윤문
    return len(text) > 40


def _call_provider(text, lang, polish=None):
    draft = google_translate.translate_text(text, lang)
    if draft:
        if _should_polish(text, polish):
            polished = _call_gemini(text, lang, draft=draft)
            if polished and _is_quality_ok(polished, lang, text):
                return polished, "hybrid"
            if _is_quality_ok(draft, lang, text):
                return draft, "google"
            # 품질 불합격이면 원문 유지 (오염 캐시 방지)
            return text, "none"
        if _is_quality_ok(draft, lang, text):
            return draft, "google"
        # Google 초벌에 Hangul이 남은 경우에만 Gemini 재시도
        polished = _call_gemini(text, lang, draft=draft)
        if polished and _is_quality_ok(polished, lang, text):
            return polished, "hybrid"
        return text, "none"
    if _should_polish(text, polish) or polish is not False:
        direct = _call_gemini(text, lang)
        if direct and _is_quality_ok(direct, lang, text):
            return direct, "gemini"
    return text, "none"


def promote_to_glossary(source_text, lang, translated_text, promoted_from="auto", hit_count=0):
    if not source_text or lang not in _LANG_NAMES:
        return None
    if not _is_quality_ok(translated_text, lang, source_text):
        return None
    if translated_text == source_text:
        return None
    h = _hash(source_text)
    row = db.session.execute(db.select(LearnedGlossary).where(LearnedGlossary.source_hash == h, LearnedGlossary.lang == lang)).scalar_one_or_none()
    if row:
        row.translated_text = translated_text
        row.promoted_from = promoted_from
        row.hit_count_at_promote = max(row.hit_count_at_promote or 0, hit_count)
    else:
        row = LearnedGlossary(
            source_hash=h,
            source_text=source_text,
            lang=lang,
            translated_text=translated_text,
            promoted_from=promoted_from,
            hit_count_at_promote=hit_count,
        )
        db.session.add(row)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning("Glossary promote failed: %s", exc)
        return None
    return row


def _maybe_promote(row):
    if not row or not _is_quality_ok(row.translated_text, row.lang, row.source_text):
        return
    if row.reviewed:
        promote_to_glossary(
            row.source_text, row.lang, row.translated_text,
            promoted_from="reviewed", hit_count=row.hit_count or 0,
        )
        return
    if (row.hit_count or 0) >= PROMOTE_THRESHOLD:
        promote_to_glossary(
            row.source_text, row.lang, row.translated_text,
            promoted_from="auto", hit_count=row.hit_count or 0,
        )


def translate(text, lang, *, remote=True, polish=None):
    """자유 텍스트 번역.

    remote=False: 용어집/캐시만 사용 (필터·캐스케이드용 — API 호출로 워커 타임아웃 방지)
    polish: True/False/None(auto). 짧은 차량명은 Google만, 긴 서술만 Gemini 윤문.
    """
    if not text or lang == "ko" or lang not in _LANG_NAMES:
        return text
    if text in load_pack(lang).values():
        return text
    static = _static_lookup(text, lang)
    if static:
        return static

    h = _hash(text)
    row = db.session.execute(db.select(TranslationCache).where(TranslationCache.source_hash == h, TranslationCache.lang == lang)).scalar_one_or_none()
    if row:
        if not _is_quality_ok(row.translated_text, lang, text):
            try:
                db.session.delete(row)
                db.session.commit()
            except Exception:
                db.session.rollback()
        else:
            row.hit_count = (row.hit_count or 0) + 1
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            _maybe_promote(row)
            return row.translated_text

    if not remote:
        # 외부 API 없이 원문 표시 — 페이지 로드/필터가 멈추지 않게
        return text

    translated, engine = _call_provider(text, lang, polish=polish)
    if translated == text or not _is_quality_ok(translated, lang, text):
        return translated

    try:
        row = TranslationCache(
            source_hash=h,
            source_text=text,
            lang=lang,
            translated_text=translated,
            hit_count=1,
            engine=engine,
        )
        db.session.add(row)
        db.session.commit()
        _maybe_promote(row)
    except Exception as exc:
        db.session.rollback()
        logger.warning("Translation cache write failed: %s", exc)
    return translated
