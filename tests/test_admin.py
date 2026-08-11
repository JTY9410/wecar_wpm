import io

from app.extensions import db
from app.models import AuctionRecord, UploadHistory
from tests.conftest import login
from tests.fixtures.make_fixture import build


def test_admin_upload_endpoint(app, client, tmp_path):
    login(client)
    path = build(str(tmp_path / "u.xlsx"))
    with open(path, "rb") as fh:
        data = {"file": (io.BytesIO(fh.read()), "20260715_data.xlsx"),
                "mode": "reset", "week_no": ""}
        resp = client.post("/admin/upload", data=data,
                           content_type="multipart/form-data")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert body["rows_ok"] == 3
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(AuctionRecord)) == 3
        assert db.session.scalar(db.select(db.func.count()).select_from(UploadHistory).where(UploadHistory.status == "SUCCESS")) == 1


def test_admin_upload_rejects_non_excel(client):
    login(client)
    data = {"file": (io.BytesIO(b"nope"), "bad.txt"), "mode": "append"}
    resp = client.post("/admin/upload", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 400


def test_developer_requires_admin(client):
    r = client.get("/admin/developer")
    assert r.status_code in (302, 401)
    login(client)
    r = client.get("/admin/developer")
    assert r.status_code == 200
    assert b"API" in r.data or "명세서".encode() in r.data


def test_user_cannot_upload(app, client):
    from app.extensions import db
    from app.models import User
    with app.app_context():
        u = User(username="dealer2", role="USER", is_approved=True)
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()
    login(client, username="dealer2", password="pw")
    resp = client.post("/admin/upload")
    assert resp.status_code == 403
