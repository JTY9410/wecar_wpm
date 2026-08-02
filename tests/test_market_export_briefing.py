"""시세 Excel export · 주간 브리핑 · AI 학습 페이지 스모크."""

from app.extensions import db as _db
from app.models import AuctionRecord, MarketSummary, User
from app.services.excel_export import export_grid_excel
from app.services.weekly_briefing import build_briefing
from tests.conftest import login


def _seed_auction(db):
    db.session.add_all([
        AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="그랜저",
            hammer_price=2500, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="그랜저",
            hammer_price=2600, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W29", maker="현대", model_name="그랜저",
            hammer_price=2400, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        MarketSummary(
            maker="현대", model_name="그랜저", car_year=2020, fuel="가솔린",
            km_bin="3~4.5만", hammer_avg=2550, sample_count=2, week_no="2026-W30",
            mom_pct=4.2,
        ),
    ])
    db.session.commit()


def test_export_grid_excel_bytes(app, db):
    _seed_auction(db)
    buf = export_grid_excel({"maker": "현대"})
    data = buf.read()
    assert data[:2] == b"PK"
    assert len(data) > 1000


def test_export_grid_requires_login(client):
    resp = client.get("/api/export/grid?maker=현대")
    assert resp.status_code in (401, 302)


def test_export_grid_ok(client, db):
    _seed_auction(db)
    login(client)
    resp = client.get("/api/export/grid?maker=현대")
    assert resp.status_code == 200
    assert "spreadsheet" in (resp.mimetype or "")
    assert resp.data[:2] == b"PK"


def test_briefing_build(app, db):
    _seed_auction(db)
    data = build_briefing()
    assert data["available"] is True
    assert data["current_period"] == "2026-W30"
    assert data["previous_period"] == "2026-W29"
    assert data["total_cur"] >= 2


def test_briefing_page(client, db):
    _seed_auction(db)
    login(client)
    resp = client.get("/briefing")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "BRIEFING" in body or "브리핑" in body


def test_ai_learning_admin_only(app, client):
    with app.app_context():
        u = User(username="dealer2", role="USER", is_approved=True)
        u.set_password("pw")
        _db.session.add(u)
        _db.session.commit()
    login(client, username="dealer2", password="pw")
    resp = client.get("/admin/ai-learning")
    assert resp.status_code in (403, 302)


def test_ai_learning_admin_ok(client, db):
    login(client)
    resp = client.get("/admin/ai-learning")
    assert resp.status_code == 200
    assert b"AI" in resp.data
