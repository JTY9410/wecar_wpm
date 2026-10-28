"""전체시세보기 — 경매차수 범위 + 트림·주행·사고 집계."""

from app.extensions import db
from app.models import AuctionRecord, User
from tests.conftest import login


def _seed_range(app):
    with app.app_context():
        db.session.add_all([
            AuctionRecord(
                week_no="2026-W28", maker="현대", model_name="그랜저",
                mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="익스클루시브",
                hammer_price=2000, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
                is_accident_free=True,
            ),
            AuctionRecord(
                week_no="2026-W29", maker="현대", model_name="그랜저",
                mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="익스클루시브",
                hammer_price=2400, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
                is_accident_free=True,
            ),
            AuctionRecord(
                week_no="2026-W30", maker="현대", model_name="그랜저",
                mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="익스클루시브",
                hammer_price=2600, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
                is_accident_free=True,
            ),
            AuctionRecord(
                week_no="2026-W30", maker="현대", model_name="그랜저",
                mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="익스클루시브",
                hammer_price=1800, car_year=2020, km_bin="6~8만", fuel="가솔린",
                is_accident_free=False,
            ),
            AuctionRecord(
                week_no="2026-W30", maker="기아", model_name="K5",
                mdetail_name="K5 DL3", grade_name="가솔린 1.6", gdetail_name="시그니처",
                hammer_price=1500, car_year=2021, km_bin="3~4.5만", fuel="가솔린",
                is_accident_free=True,
            ),
        ])
        db.session.commit()


def test_full_market_requires_login(client):
    resp = client.get("/market/all")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


def test_approved_user_can_open_full_market(app, client):
    with app.app_context():
        u = User(username="dealer_full", role="USER", is_approved=True)
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()
    login(client, username="dealer_full", password="pw")
    resp = client.get("/market/all")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "전체시세" in html
    assert 'id="weekFrom"' in html
    assert 'id="weekTo"' in html
    assert 'id="fullSearch"' in html
    assert 'id="qWord"' in html
    assert "nav_market_full" not in html or "전체시세" in html


def test_full_market_nav_visible_to_user(app, client):
    with app.app_context():
        u = User(username="dealer_nav", role="USER", is_approved=True)
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()
    login(client, username="dealer_nav", password="pw")
    html = client.get("/").get_data(as_text=True)
    assert "/market/all" in html
    assert "전체시세" in html


def test_weeks_and_full_grid_for_user(app, client):
    _seed_range(app)
    with app.app_context():
        u = User(username="dealer_grid", role="USER", is_approved=True)
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()
    login(client, username="dealer_grid", password="pw")
    weeks = client.get("/market/api/weeks").get_json()
    assert weeks["ok"] is True
    assert "2026-W29" in weeks["weeks"]
    assert "2026-W30" in weeks["weeks"]

    data = client.get("/market/api/full-grid", query_string={
        "week_from": "2026-W29",
        "week_to": "2026-W30",
        "maker": "현대",
        "model_name": "그랜저",
        "fuel": "가솔린",
        "car_year": "2020",
    }).get_json()
    assert data["ok"] is True
    assert data["count"] >= 2
    combos = {(r["km_bin"], r["is_accident_free_flag"]) for r in data["rows"]}
    assert ("3~4.5만", True) in combos
    assert ("6~8만", False) in combos
    avg_row = next(r for r in data["rows"] if r["km_bin"] == "3~4.5만" and r["is_accident_free_flag"])
    assert avg_row["hammer_avg"] == 2500
    assert avg_row["sample_count"] == 2
    assert all(r["maker"] == "현대" for r in data["rows"])
    assert all("2026-W28" not in (r.get("weeks") or []) for r in data["rows"])


def test_full_grid_q_word_matches_trim_fields(app, client):
    _seed_range(app)
    login(client)
    data = client.get("/market/api/full-grid", query_string={
        "week_from": "2026-W28",
        "week_to": "2026-W30",
        "q": "K5",
    }).get_json()
    assert data["ok"] is True
    assert data["count"] == 1
    assert data["rows"][0]["model_name"] == "K5"


def test_full_grid_requires_weeks(client):
    login(client)
    resp = client.get("/market/api/full-grid")
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
