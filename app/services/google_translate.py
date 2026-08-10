"""Google Cloud Translation API v2 클라이언트.

관리자 페이지(LLM 설정)에서 API 키를 등록하면 활성화된다. 키는 기존 LLMConfig
테이블에 provider="google_translate" 로 저장해 별도 마이그레이션 없이 재사용한다.
키 미설정/호출 실패 시 None을 반환해 상위(i18n_translate)에서 Gemini 또는
원문 패스스루로 넘어간다.
"""
import logging

import requests

from app.extensions import db
from app.models import LLMConfig
from config import Config

logger = logging.getLogger(__name__)

_ENDPOINT = "https://translation.googleapis.com/language/translate/v2"
_PROVIDER = "google_translate"


def resolve_api_key() -> str:
    row = db.session.execute(db.select(LLMConfig).where(LLMConfig.provider == _PROVIDER)).scalar_one_or_none()
    if row and row.api_key:
        return row.api_key.strip()
    return (Config.GOOGLE_TRANSLATE_API_KEY or "").strip()


def is_configured() -> bool:
    return bool(resolve_api_key())


def save_api_key(api_key=None, clear_key=False):
    row = db.session.execute(db.select(LLMConfig).where(LLMConfig.provider == _PROVIDER)).scalar_one_or_none()
    if row is None:
        row = LLMConfig(provider=_PROVIDER, is_active=False)
        db.session.add(row)
    if clear_key:
        row.api_key = None
    elif api_key is not None and str(api_key).strip():
        row.api_key = str(api_key).strip()
    db.session.commit()
    return row


def translate_text(text: str, target_lang: str, source_lang: str = "ko") -> str | None:
    """번역 성공 시 문자열, 키 미설정/실패 시 None."""
    api_key = resolve_api_key()
    if not api_key or not text:
        return None
    try:
        resp = requests.post(
            _ENDPOINT,
            params={"key": api_key},
            json={"q": text, "target": target_lang, "source": source_lang, "format": "text"},
            timeout=10,
        )
        resp.raise_for_status()
        translations = resp.json()["data"]["translations"]
        return translations[0]["translatedText"] or None
    except Exception as exc:
        logger.warning("Google Translate failed: %s", exc)
        return None


def test_connection() -> dict:
    """관리자 설정 화면의 '연결 테스트' 버튼용 — 실제 API 호출로 키 유효성을 확인."""
    if not is_configured():
        return {"ok": False, "error": "API 키가 설정되지 않았습니다."}
    sample = "연결 테스트"
    try:
        resp = requests.post(
            _ENDPOINT,
            params={"key": resolve_api_key()},
            json={"q": sample, "target": "en", "source": "ko", "format": "text"},
            timeout=10,
        )
        if resp.status_code != 200:
            detail = ""
            try:
                detail = resp.json().get("error", {}).get("message", "")
            except Exception:
                pass
            return {"ok": False, "error": detail or f"HTTP {resp.status_code}"}
        translated = resp.json()["data"]["translations"][0]["translatedText"]
        return {"ok": True, "sample": sample, "translated": translated}
    except Exception as exc:
        logger.warning("Google Translate connection test failed: %s", exc)
        return {"ok": False, "error": str(exc)}
