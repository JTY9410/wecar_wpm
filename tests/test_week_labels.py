"""경매차수 라벨(일자 포함) · 시세 그리드 차수 필수."""

from app.extensions import db
from app.models import AuctionRecord
from app.services import market_query
from tests.conftest import login


def _seed_weeks(app):
    with app.app_context():
        db.session.add_all([
            AuctionRecord(
                week_no="2026-W27", auction_date="2026-07-07",
                maker="현대", model_name="그랜저", mdetail_name="그랜저 IG",
                grade_name="가솔린 2.5", gdetail_name="익스클루시브",
                car_name="현대 그랜저 IG 익스클루시브",
                hammer_price=2000, car_year=2020, km_bin="3만~4만km", fuel="가솔린",
                accident_grade="무사고", is_accident_free=True, awd="2WD",
            ),
            AuctionRecord(
                week_no="2026-W28", auction_date="2026-07-14",
                maker="현대", model_name="그랜저", mdetail_name="그랜저 IG",
                grade_name="가솔린 2.5", gdetail_name="익스클루시브",
                car_name="현대 그랜저 IG 익스클루시브",
                hammer_price=2200, car_year=2020, km_bin="3만~4만km", fuel="가솔린",
                accident_grade="무사고", is_accident_free=True, awd="2WD",
            ),
            AuctionRecord(
                week_no="2026-W28", auction_date="2026-07-14",
                maker="폭스바겐", model_name="CC", mdetail_name="CC",
                grade_name="2.0 TDI", gdetail_name="블루모션",
                car_name="폭스바겐 CC 2.0 TDI",
                hammer_price=300, car_year=2015, km_bin="15만~16만km", fuel="디젤",
                accident_grade="단순교환", is_accident_free=False, awd="2WD",
            ),
        ])
        db.session.commit()


def test_week_label_includes_korean_month_day(app, db):
    _seed_weeks(app)
    weeks = market_query.weeks()
    assert weeks
    assert all(isinstance(w, dict) and "value" in w and "label" in w for w in weeks)
    w27 = next(w for w in weeks if w["value"] == "2026-W27")
    assert w27["label"] == "2026-W27(7월7일)"
    w28 = next(w for w in weeks if w["value"] == "2026-W28")
    assert w28["label"] == "2026-W28(7월14일)"


def test_grid_requires_week_range(app, client):
    _seed_weeks(app)
    login(client)
    resp = client.get("/api/grid?car_name=그랜저")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


def test_grid_filters_by_week_range_and_car_name(app, db):
    _seed_weeks(app)
    rows = market_query.grid(
        week_from="2026-W27", week_to="2026-W28", car_name="그랜저",
    )
    assert rows
    assert all("그랜저" in (r.get("car_name") or "") for r in rows)
    assert rows[0]["hammer_avg"] == 2100.0  # (2000+2200)/2
    assert rows[0]["sample_count"] == 2

    only28 = market_query.grid(
        week_from="2026-W28", week_to="2026-W28", car_name="CC",
    )
    assert len(only28) == 1
    assert only28[0]["accident_grade"] == "단순교환"
    assert only28[0]["hammer_avg"] == 300.0


def test_market_page_has_week_selects(app, client):
    _seed_weeks(app)
    login(client)
    html = client.get("/").get_data(as_text=True)
    assert 'id="weekFrom"' in html
    assert 'id="weekTo"' in html
    assert "2026-W27(7월7일)" in html
