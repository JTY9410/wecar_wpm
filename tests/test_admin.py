import io
import re
import threading
import time
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

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


def test_admin_dashboard_file_input_not_inside_dropzone(client):
    """Dropzone textContent/click must not destroy or recurse on the file input."""
    login(client)
    html = client.get("/admin/").get_data(as_text=True)
    dz = re.search(r'<div id="dropzone"[^>]*>(.*?)</div>', html, re.S)
    assert dz, "dropzone missing"
    assert 'id="file"' not in dz.group(1)
    assert re.search(r'<input[^>]*id="file"', html)


def test_admin_upload_returns_json_when_train_fails(app, client, tmp_path):
    login(client)
    path = build(str(tmp_path / "u.xlsx"))
    with open(path, "rb") as fh:
        data = {"file": (io.BytesIO(fh.read()), "20260715_data.xlsx"),
                "mode": "reset", "week_no": ""}
        with patch("app.routes.admin.PriceModel") as pm:
            pm.return_value.train.side_effect = OSError("Read-only file system")
            resp = client.post("/admin/upload", data=data,
                               content_type="multipart/form-data")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body is not None
    assert body["ok"] is True
    assert body["rows_ok"] == 3
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(AuctionRecord)) == 3


def test_developer_requires_admin(client):
    r = client.get("/admin/developer")
    assert r.status_code in (302, 401)
    login(client)
    r = client.get("/admin/developer")
    assert r.status_code == 200
    assert b"API" in r.data or "명세서".encode() in r.data


def test_analysis_logic_page_requires_admin(client):
    r = client.get("/admin/analysis-logic")
    assert r.status_code in (302, 401)
    login(client)
    r = client.get("/admin/analysis-logic")
    assert r.status_code == 200
    assert b"analysis-logic" in r.data or "분석".encode() in r.data or b"pipeline" in r.data.lower()


def test_anonymous_upload_returns_json_401(client):
    """fetch('/admin/upload') must get JSON 401, not an HTML login redirect."""
    resp = client.post("/admin/upload")
    assert resp.status_code == 401
    body = resp.get_json()
    assert body is not None
    assert body.get("ok") is False
    assert "인증" in (body.get("error") or "")


def test_sqlite_uses_wal(app):
    mode = db.session.execute(text("PRAGMA journal_mode")).scalar()
    assert str(mode).lower() == "wal"


def test_admin_upload_returns_without_waiting_for_train(app, client, tmp_path):
    """Ingest JSON must return even if model training blocks (avoids proxy 502)."""
    release = threading.Event()

    def hang_train(_self=None):
        release.wait(timeout=8)
        return {"trained": True, "count": 0}

    login(client)
    path = build(str(tmp_path / "u.xlsx"))
    t0 = time.monotonic()
    with patch("app.routes.admin.PriceModel") as pm, patch("app.routes.admin.HedonicModel") as hm:
        pm.return_value.train.side_effect = hang_train
        hm.return_value.train.side_effect = hang_train
        with open(path, "rb") as fh:
            data = {"file": (io.BytesIO(fh.read()), "20260715_data.xlsx"),
                    "mode": "reset", "week_no": ""}
            resp = client.post("/admin/upload", data=data,
                               content_type="multipart/form-data")
    elapsed = time.monotonic() - t0
    release.set()
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert body["rows_ok"] == 3
    assert elapsed < 3


def test_compose_publishes_nginx_proxy():
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "nginx:" in text
    assert "8090:80" in text
    assert "8090:5000" not in text


def test_service_worker_cache_bumped(client):
    js = client.get("/service-worker.js").get_data(as_text=True)
    assert "wecar-wpm-v1" not in js
    assert "wecar-wpm-v2" in js


def test_admin_dashboard_upload_js_handles_gateway_errors(client):
    login(client)
    html = client.get("/admin/").get_data(as_text=True)
    assert "redirect: 'manual'" in html
    assert "서버가 업로드를 처리하지 못했습니다" in html


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
