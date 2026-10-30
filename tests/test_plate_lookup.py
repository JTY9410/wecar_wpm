"""차량번호조회 · 오토업→시세 매핑 · 관리자 API 키."""

from app.extensions import db
from app.models import AuctionRecord, MarketSummary
from app.services import car_info_api, diag_trim_resolve
from tests.conftest import login


SAMPLE_DTO = {
    "diag_info_api": "autoup",
    "diag_car_id": "KPBXH3AP1GP051826",
    "diag_company_idx": 5,
    "diag_company": "현대",
    "diag_model_idx": 100,
    "diag_model": "그랜저",
    "diag_submodel_idx": 200,
    "diag_submodel": "그랜저 IG (16~19년)",
    "diag_grade_idx": 300,
    "diag_grade": "가솔린 2.5",
    "diag_subgrade_idx": 400,
    "diag_subgrade": "익스클루시브",
    "diag_year": 2020,
    "diag_fuel": "휘발유",
    "diag_color": "white",
    "diag_registred_date": "2019-05-01",
    "diag_new_price": 35000000,
}


def _seed_summary(app):
    with app.app_context():
        db.session.add(MarketSummary(
            maker="현대", model_name="그랜저", mdetail_name="그랜저 IG",
            grade_name="가솔린 2.5", gdetail_name="익스클루시브",
            car_year=2020, fuel="가솔린", km_bin="3~4.5만",
            hammer_avg=2550, sample_count=2, week_no="2026-W30",
            is_accident_free=True,
        ))
        db.session.add(AuctionRecord(
            week_no="2026-W30", auction_date="2026-07-28",
            maker="현대", model_name="그랜저", mdetail_name="그랜저 IG",
            grade_name="가솔린 2.5", gdetail_name="익스클루시브",
            car_name="현대 그랜저 IG 익스클루시브",
            car_year=2020, fuel="가솔린", km_bin="3~4.5만",
            hammer_price=2550, accident_grade="무사고", is_accident_free=True,
        ))
        db.session.commit()


def test_market_page_has_trim_and_plate_modes(client):
    login(client)
    html = client.get("/").get_data(as_text=True)
    assert "세부등급조회" in html
    assert "차량번호조회" in html
    assert 'id="plateCarNo"' in html
    assert 'id="plateSearch"' in html
    assert "/api/lookup/plate" in html or "plateSearch" in html


def test_plate_lookup_requires_car_no(client):
    login(client)
    resp = client.get("/api/lookup/plate")
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_plate_lookup_without_key(client, monkeypatch):
    login(client)
    monkeypatch.setattr(car_info_api, "is_configured", lambda: False)
    monkeypatch.setattr(
        car_info_api, "fetch_car_info",
        lambda *a, **k: {"ok": False, "error": "위카 차량정보 API 인증키가 설정되지 않았습니다.", "car_no": "12가3456"},
    )
    resp = client.get("/api/lookup/plate", query_string={"car_no": "12가3456"})
    assert resp.status_code == 400
    assert "인증키" in resp.get_json()["error"]


def test_resolve_maps_fuel_and_trim(app, db):
    _seed_summary(app)
    with app.app_context():
        dto = car_info_api.normalize_dto(SAMPLE_DTO)
        resolved = diag_trim_resolve.resolve_market_filters(dto)
        assert resolved["ok"] is True
        assert resolved["filters"]["maker"] == "현대"
        assert resolved["filters"]["model_name"] == "그랜저"
        assert resolved["filters"]["gdetail_name"] == "익스클루시브"
        assert resolved["filters"]["fuel"] == "가솔린"
        assert resolved["filters"]["car_year"] == 2020


def test_plate_lookup_returns_market_rows(app, client, monkeypatch):
    _seed_summary(app)
    login(client)

    def fake_fetch(car_no, **kwargs):
        return {
            "ok": True,
            "car_no": "241우7738",
            "dto": car_info_api.normalize_dto(SAMPLE_DTO),
            "cached": False,
            "fetched_at": "2026-10-28T00:00:00+00:00",
        }

    monkeypatch.setattr(car_info_api, "fetch_car_info", fake_fetch)
    monkeypatch.setattr(car_info_api, "is_configured", lambda: True)
    resp = client.get("/api/lookup/plate", query_string={"car_no": "241우7738"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["count"] >= 1
    assert data["rows"][0]["maker"] == "현대"
    assert data["mapping"]["filters"]["gdetail_name"] == "익스클루시브"


def test_admin_car_info_settings(client):
    login(client)
    resp = client.post("/admin/car-info/settings", data={
        "api_key": "test-auth-key-123456",
        "api_url": "https://diag.wecarmobility.co.kr/api/get_car_info",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert car_info_api.is_configured()
    assert "get_car_info" in car_info_api.resolve_api_url()

    html = client.get("/admin/").get_data(as_text=True)
    assert "차량정보 API" in html
    assert "오토업↔시세 매핑" in html
