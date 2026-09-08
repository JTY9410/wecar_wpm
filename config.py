"""SSOT configuration. Every setting/path/key is read here from .env only."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _abs(path: str) -> str:
    p = Path(path)
    return str(p if p.is_absolute() else (BASE_DIR / p))


class Config:
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    APP_NAME = os.getenv("APP_NAME", "도매시세분석")
    SERVICE_ID = os.getenv("SERVICE_ID", "wecarcar1")
    BRAND_MARK = os.getenv("BRAND_MARK", "WPM")
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")

    KS_API_BASE_URL = os.getenv("KS_API_BASE_URL", "")
    FALLBACK_API_BASE_URL = os.getenv("FALLBACK_API_BASE_URL", "")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///instance/wecarcar1_auto.db")
    if DATABASE_URL.startswith("sqlite:///"):
        _raw = DATABASE_URL.replace("sqlite:///", "")
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{_abs(_raw)}"
    else:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        **({"connect_args": {"timeout": 30, "check_same_thread": False}} if SQLALCHEMY_DATABASE_URI.startswith("sqlite") else {}),
    }
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(100 * 1024 * 1024)))

    IMAGE_STORAGE_PATH = _abs(os.getenv("IMAGE_STORAGE_PATH", "./instance/storage/car_images"))
    EXCEL_UPLOAD_PATH = _abs(os.getenv("EXCEL_UPLOAD_PATH", "./instance/storage/excel_uploads"))
    CHROMA_PATH = _abs(os.getenv("CHROMA_PATH", "./instance/storage/chroma"))
    MODEL_PATH = _abs(os.getenv("MODEL_PATH", "./instance/car_price_model.pkl"))
    HEDONIC_MODEL_PATH = _abs(os.getenv("HEDONIC_MODEL_PATH", "./instance/hedonic_model.pkl"))

    INIT_ADMIN_USERNAME = os.getenv("INIT_ADMIN_USERNAME", "wecar")
    INIT_ADMIN_PASSWORD = os.getenv("INIT_ADMIN_PASSWORD", "1004wecar")

    ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "0") == "1"
    SYNC_BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "500"))

    # Business constraints (PRD §2.2 / §5)
    RATE_LIMIT_DAILY = 20
    SYNC_HOURS = [9, 13, 18]
    API_TIMEOUT = 120
    KM_BUCKET_STEP = 15000
    KM_BUCKET_MAX = 200000
    LEVENSHTEIN_THRESHOLD = 0.85
    SEARCH_PAGE_SIZE = 24
    GEMINI_MODEL = "gemini-2.5-flash"
    SUPPORTED_LANGS = ["ko", "en", "ja"]

    LISTINGS_PATH = "listings"
    IMAGE_URL_PREFIX = "/static/storage/car_images"
    # Wholesale API key for future PM (or other) consumers — inbound only.
    EXTERNAL_API_KEY = os.getenv("EXTERNAL_API_KEY", "")
    # Runtime mode: standalone (default) | linked (when a PM consumer is wired)
    INTEGRATION_MODE = os.getenv("INTEGRATION_MODE", "standalone")
    TRUST_PROXY = os.getenv("TRUST_PROXY", "0") == "1"
    CAR2_CODES_BASE_URL = os.getenv("CAR2_CODES_BASE_URL", "http://host.docker.internal:8080")

    @classmethod
    def ensure_dirs(cls):
        for p in (cls.IMAGE_STORAGE_PATH, cls.EXCEL_UPLOAD_PATH, cls.CHROMA_PATH):
            Path(p).mkdir(parents=True, exist_ok=True)
        Path(cls.MODEL_PATH).parent.mkdir(parents=True, exist_ok=True)
        Path(cls.HEDONIC_MODEL_PATH).parent.mkdir(parents=True, exist_ok=True)
