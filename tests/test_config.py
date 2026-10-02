import pytest

from config import BASE_DIR, Config, assert_secret_key_safe

LEAKED_SECRET = "ks_ai_secure_secret_key_2026"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_business_constants():
    assert Config.SYNC_HOURS == [9, 13, 18]
    assert Config.RATE_LIMIT_DAILY == 20
    assert Config.API_TIMEOUT == 120
    assert Config.KM_BUCKET_STEP == 15000


def test_rejects_leaked_or_empty_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_secret_key_safe(LEAKED_SECRET, testing=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_secret_key_safe("change-me", testing=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_secret_key_safe("", testing=False)


def test_allows_insecure_secret_only_when_testing():
    assert_secret_key_safe(LEAKED_SECRET, testing=True)
    assert_secret_key_safe("a-unique-random-secret", testing=False)


def test_committed_files_do_not_contain_leaked_secret():
    example = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
    requirements = (BASE_DIR / "요구사항.md").read_text(encoding="utf-8")
    assert LEAKED_SECRET not in example
    assert LEAKED_SECRET not in requirements
