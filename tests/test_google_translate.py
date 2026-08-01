"""Google Cloud Translation API 클라이언트 — LLMConfig 기반 키 저장/조회/호출 테스트."""
from app.services import google_translate


def test_resolve_api_key_prefers_db_over_env(app, db, monkeypatch):
    monkeypatch.setattr("config.Config.GOOGLE_TRANSLATE_API_KEY", "env-key")
    assert google_translate.resolve_api_key() == "env-key"

    google_translate.save_api_key(api_key="db-key")
    assert google_translate.resolve_api_key() == "db-key"
    assert google_translate.is_configured() is True


def test_save_api_key_clear(app, db):
    google_translate.save_api_key(api_key="db-key")
    assert google_translate.is_configured() is True
    google_translate.save_api_key(clear_key=True)
    assert google_translate.resolve_api_key() == ""


def test_translate_text_without_key_returns_none(app, db):
    assert google_translate.translate_text("안녕하세요", "en") is None


def test_translate_text_calls_api_and_parses_response(app, db, monkeypatch):
    google_translate.save_api_key(api_key="test-key")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"translations": [{"translatedText": "Hello"}]}}

    monkeypatch.setattr(google_translate.requests, "post", lambda *a, **k: FakeResponse())
    assert google_translate.translate_text("안녕", "en") == "Hello"


def test_translate_text_returns_none_on_failure(app, db, monkeypatch):
    google_translate.save_api_key(api_key="test-key")

    def boom(*a, **k):
        raise RuntimeError("network error")

    monkeypatch.setattr(google_translate.requests, "post", boom)
    assert google_translate.translate_text("안녕", "en") is None
