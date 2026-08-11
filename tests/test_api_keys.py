from app.services import api_keys


def test_issue_and_verify(db, app):
    with app.app_context():
        row, plain = api_keys.issue_api_key("partner", created_by="wecar")
        assert plain.startswith("wpm_")
        assert api_keys.verify_api_key(plain) is not None
        assert api_keys.verify_api_key("wrong") is None


def test_revoke_rejects(db, app):
    with app.app_context():
        row, plain = api_keys.issue_api_key("x", created_by="wecar")
        assert api_keys.revoke_api_key(row.id) is True
        assert api_keys.verify_api_key(plain) is None


def test_env_fallback(client, app):
    app.config["EXTERNAL_API_KEY"] = "env-legacy-key"
    r = client.get("/api/v1/wholesale/codes/makers", headers={"X-API-Key": "env-legacy-key"})
    assert r.status_code == 200
