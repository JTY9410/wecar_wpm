"""글로벌 다국어 번역 + 로컬 캐시 (PRD §6.3). Passthrough when no API key."""
import hashlib
import json
import os

from config import Config
from app.extensions import db
from app.models import TranslationCache

_I18N_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "i18n")


def load_pack(lang):
    if lang not in Config.SUPPORTED_LANGS:
        lang = "ko"
    path = os.path.join(_I18N_DIR, f"{lang}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def translate(text, lang):
    """Translate free-form text with local cache. Falls back to source text."""
    if not text or lang == "ko":
        return text
    h = _hash(text)
    row = TranslationCache.query.filter_by(source_hash=h, lang=lang).first()
    if row:
        return row.translated_text

    translated = _call_provider(text, lang)
    db.session.add(TranslationCache(source_hash=h, source_text=text, lang=lang,
                                    translated_text=translated))
    db.session.commit()
    return translated


def _call_provider(text, lang):
    if not Config.DEEPL_API_KEY:
        return text  # graceful passthrough
    try:
        import requests
        resp = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={"auth_key": Config.DEEPL_API_KEY, "text": text,
                  "target_lang": "EN" if lang == "en" else "JA"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["translations"][0]["text"]
    except Exception:
        return text
