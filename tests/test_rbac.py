from app.extensions import db
from app.models import User
from tests.conftest import login


def _make_user(app):
    with app.app_context():
        u = User(username="dealer", role="USER", is_approved=True)
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()


def test_login_success(client):
    resp = login(client)
    assert resp.status_code == 200


def test_login_bad_password(client):
    resp = login(client, password="nope")
    assert "올바르지 않습니다" in resp.get_data(as_text=True)


def test_user_blocked_from_admin(app, client):
    _make_user(app)
    login(client, username="dealer", password="pw")
    resp = client.post("/admin/sync")
    assert resp.status_code == 403


def test_admin_allowed(client):
    login(client)
    resp = client.get("/admin/")
    assert resp.status_code == 200


def test_anonymous_admin_api_401(client):
    resp = client.post("/admin/retrain")
    assert resp.status_code in (401, 302)
