"""시세 Excel export · 주간 브리핑 · AI 학습 페이지 스모크."""

from app.extensions import db as _db
from app.models import AuctionRecord, MarketSummary, User
from app.services.excel_export import export_grid_excel
from app.services.weekly_briefing import build_briefing, fetch_trim_auction_details
from tests.conftest import login


def _seed_auction(db):
    db.session.add_all([
        AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="그랜저",
            mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="익스클루시브",
            hammer_price=2500, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="그랜저",
            mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="익스클루시브",
            hammer_price=2600, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W29", maker="현대", model_name="그랜저",
            mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="익스클루시브",
            hammer_price=2400, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W29", maker="현대", model_name="그랜저",
            mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="익스클루시브",
            hammer_price=2400, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        # 같은 모델·다른 세부등급 — 모델명 기준이면 합쳐지지만 세부등급 기준이면 분리
        AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="그랜저",
            mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="캘리그래피",
            hammer_price=3200, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="그랜저",
            mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="캘리그래피",
            hammer_price=3200, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W29", maker="현대", model_name="그랜저",
            mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="캘리그래피",
            hammer_price=2800, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W29", maker="현대", model_name="그랜저",
            mdetail_name="그랜저 IG", grade_name="가솔린 2.5", gdetail_name="캘리그래피",
            hammer_price=2800, car_year=2020, km_bin="3~4.5만", fuel="가솔린",
        ),
        # 표본 1건씩 — 변동은 크지만 가격 특이사항에서 제외
        AuctionRecord(
            week_no="2026-W30", maker="기아", model_name="모닝",
            mdetail_name="모닝", grade_name="가솔린", gdetail_name="베이직",
            hammer_price=900, car_year=2019, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W29", maker="기아", model_name="모닝",
            mdetail_name="모닝", grade_name="가솔린", gdetail_name="베이직",
            hammer_price=300, car_year=2019, km_bin="3~4.5만", fuel="가솔린",
        ),
        # 표본은 충분하지만 변동 < 5% — 가격 특이사항에서 제외
        AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="아반떼",
            mdetail_name="아반떼 CN7", grade_name="가솔린 1.6", gdetail_name="스마트",
            hammer_price=1020, car_year=2021, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="아반떼",
            mdetail_name="아반떼 CN7", grade_name="가솔린 1.6", gdetail_name="스마트",
            hammer_price=1020, car_year=2021, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W29", maker="현대", model_name="아반떼",
            mdetail_name="아반떼 CN7", grade_name="가솔린 1.6", gdetail_name="스마트",
            hammer_price=1000, car_year=2021, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W29", maker="현대", model_name="아반떼",
            mdetail_name="아반떼 CN7", grade_name="가솔린 1.6", gdetail_name="스마트",
            hammer_price=1000, car_year=2021, km_bin="3~4.5만", fuel="가솔린",
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
    assert data.get("compare_basis") == "gdetail"


def test_briefing_compares_by_gdetail_not_model(app, db):
    """같은 모델이라도 세부등급이 다르면 전주대비를 따로 계산한다."""
    _seed_auction(db)
    data = build_briefing()
    by_trim = {r["gdetail_name"]: r for r in data["rows"]}
    assert "익스클루시브" in by_trim
    assert "캘리그래피" in by_trim
    # 익스클루시브: ((2500+2600)/2 - 2400)/2400 = 6.25% → 6.2
    assert by_trim["익스클루시브"]["price_pct"] == 6.2
    # 캘리그래피: (3200-2800)/2800 ≈ 14.3%
    assert by_trim["캘리그래피"]["price_pct"] == 14.3
    # 모델명으로 합치면 한 줄이 되어야 하지만, 세부등급 기준이면 2줄
    granzer_rows = [r for r in data["rows"] if r["model_name"] == "그랜저"]
    assert len(granzer_rows) == 2


def test_price_alerts_only_real_anomalies(app, db):
    """가격 특이사항은 ±5% 이상 + 금주·전주 표본 각 2건 이상만 포함한다."""
    _seed_auction(db)
    data = build_briefing()
    alert_trims = {r["gdetail_name"] for r in data["price_alerts"]}
    assert "익스클루시브" in alert_trims
    assert "캘리그래피" in alert_trims
    # 표본 1건씩(모닝 베이직) — 변동 크더라도 제외
    assert "베이직" not in alert_trims
    # 표본은 충분하지만 2%대 변동 — 제외
    assert "스마트" not in alert_trims
    assert all(r["price_flag"] for r in data["price_alerts"])
    assert all(
        r["cur_count"] >= 2 and r["prev_count"] >= 2 for r in data["price_alerts"]
    )


def test_briefing_page(client, db):
    _seed_auction(db)
    login(client)
    resp = client.get("/briefing")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "BRIEFING" in body or "브리핑" in body
    assert "익스클루시브" in body or "세부" in body
    assert "briefing-detail-btn" in body or "세부현황" in body
    # 스크립트는 Bootstrap 로드 이후(scripts 블록)에 있어야 보기 버튼이 동작한다
    bootstrap_idx = body.find("bootstrap.bundle.min.js")
    assert body.count("briefing-detail-btn") >= 2
    assert "getOrCreateInstance" in body
    assert bootstrap_idx != -1
    assert body.rfind("openDetail") > bootstrap_idx


def test_fetch_trim_auction_details(app, db):
    _seed_auction(db)
    data = fetch_trim_auction_details(
        current_week="2026-W30",
        previous_week="2026-W29",
        maker="현대",
        model_name="그랜저",
        mdetail_name="그랜저 IG",
        grade_name="가솔린 2.5",
        gdetail_name="익스클루시브",
    )
    assert data["ok"] is True
    assert data["current_count"] == 2
    assert data["previous_count"] == 2
    assert all(r["gdetail_name"] == "익스클루시브" for r in data["current_items"])
    # 다른 세부등급(캘리그래피)은 포함되지 않음
    assert all(r["hammer_price"] != 3200 for r in data["current_items"])


def test_briefing_details_api(client, db):
    _seed_auction(db)
    login(client)
    resp = client.get(
        "/briefing/api/details"
        "?current_week=2026-W30&previous_week=2026-W29"
        "&maker=현대&model_name=그랜저&mdetail_name=그랜저 IG"
        "&grade_name=가솔린 2.5&gdetail_name=익스클루시브"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["current_count"] == 2
    assert data["previous_count"] == 2


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
