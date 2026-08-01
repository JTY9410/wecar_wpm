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
    row = LLMConfig.query.filter_by(provider=_PROVIDER).first()
    if row and row.api_key:
        return row.api_key.strip()
    return (Config.GOOGLE_TRANSLATE_API_KEY or "").strip()


def is_configured() -> bool:
    return bool(resolve_api_key())


def save_api_key(api_key=None, clear_key=False):
    row = LLMConfig.query.filter_by(provider=_PROVIDER).first()
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
