from unittest.mock import patch

from app.models import LLMConfig
from app.services import llm_hub
from app.services.llm_hub import (
    LLMError, OpenAIProvider, ClaudeProvider,
    save_provider_settings, set_active,
)


def test_openai_provider_calls_api(app, db, monkeypatch):
    save_provider_settings("openai", api_key="sk-test-openai-key-123456",
                           model_name="gpt-4o-mini")

    class Resp:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "정성 요약입니다."}}]}
        text = "ok"

    monkeypatch.setattr(llm_hub.requests, "post", lambda *a, **k: Resp())
    text = OpenAIProvider().generate("시세 요약해줘")
    assert "정성" in text


def test_claude_provider_calls_api(app, db, monkeypatch):
    save_provider_settings("claude", api_key="sk-ant-test-key-123456",
                           model_name="claude-3-5-sonnet-20241022")

    class Resp:
        status_code = 200
        def json(self):
            return {"content": [{"type": "text", "text": "Claude 분석"}]}
        text = "ok"

    monkeypatch.setattr(llm_hub.requests, "post", lambda *a, **k: Resp())
    assert "Claude" in ClaudeProvider().generate("요약")


def test_openai_missing_key(app, db):
    save_provider_settings("openai", clear_key=True)
    with patch.object(llm_hub.Config, "OPENAI_API_KEY", ""):
        try:
            OpenAIProvider().generate("x")
            assert False
        except LLMError as exc:
            assert "미설정" in str(exc)


def test_switch_and_status(app, db):
    set_active("openai")
    assert llm_hub.active_provider_name() == "openai"
    status = llm_hub.key_status()
    assert any(s["provider"] == "openai" and s["is_active"] for s in status)


def test_admin_llm_settings_endpoint(client, app):
    from tests.conftest import login
    login(client)
    resp = client.post("/admin/llm/settings", data={
        "provider": "gemini",
        "api_key": "AIzaSyTestKey1234567890",
        "model_name": "gemini-2.5-flash",
    })
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    with app.app_context():
        row = LLMConfig.query.filter_by(provider="gemini").first()
        assert row.api_key.startswith("AIza")


def test_admin_llm_test_graceful(client, app, monkeypatch):
    from tests.conftest import login
    login(client)
    monkeypatch.setattr(llm_hub, "test_provider",
                        lambda name=None: {"ok": False, "provider": "gemini",
                                           "error": "키 없음"})
    resp = client.post("/admin/llm/test", data={"provider": "gemini"})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_summary_without_key_graceful(client, app):
    from tests.conftest import login
    from app.models import MarketSummary
    from app.extensions import db as _db
    with app.app_context():
        _db.session.add(MarketSummary(
            car_code="c", maker="현대", model_name="쏘나타", car_year=2020,
            imported="수출", is_accident_free=True, km_bin="0만~1.5만km",
            start_avg=100, hammer_avg=120, sample_count=1, week_no="2026-W29",
        ))
        _db.session.commit()
        # clear keys
        for row in LLMConfig.query.all():
            row.api_key = None
        _db.session.commit()
    with patch.object(llm_hub.Config, "GEMINI_API_KEY", ""):
        with patch.object(llm_hub.Config, "OPENAI_API_KEY", ""):
            with patch.object(llm_hub.Config, "ANTHROPIC_API_KEY", ""):
                login(client)
                resp = client.post("/admin/llm/summary")
                body = resp.get_json()
                assert body["ok"] is False
                assert body["error"] == "임시 리포트 생성 불가능"
