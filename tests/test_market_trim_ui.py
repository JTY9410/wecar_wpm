"""세부등급조회 — 기본/상세검색 배치 · 매트릭스 완화."""

from app.extensions import db
from app.models import AuctionRecord
from app.services import market_query
from tests.conftest import login


def _seed(app):
    with app.app_context():
        db.session.add_all([
            AuctionRecord(
                week_no="2026-W30", auction_date="2026-07-28",
                maker="현대", model_name="그랜저", mdetail_name="그랜저 IG",
                grade_name="가솔린 2.5", gdetail_name="익스클루시브",
                car_name="현대 그랜저 IG 익스클루시브",
                hammer_price=2500, car_year=2020, km_bin="3만~4만km", fuel="가솔린",
                accident_grade="무사고", is_accident_free=True,
            ),
            AuctionRecord(
                week_no="2026-W30", auction_date="2026-07-28",
                maker="현대", model_name="그랜저", mdetail_name="그랜저 IG",
                grade_name="가솔린 2.5", gdetail_name="익스클루시브",
                car_name="현대 그랜저 IG 익스클루시브",
                hammer_price=1800, car_year=2019, km_bin="8만~9만km", fuel="가솔린",
                accident_grade="무사고", is_accident_free=True,
            ),
            AuctionRecord(
                week_no="2026-W30", auction_date="2026-07-28",
                maker="폭스바겐", model_name="CC", mdetail_name="CC",
                grade_name="2.0 TDI", gdetail_name="블루모션",
                car_name="폭스바겐 CC 2.0 TDI",
                hammer_price=300, car_year=2015, km_bin="15만~16만km", fuel="디젤",
                accident_grade="단순교환", is_accident_free=False,
            ),
        ])
        db.session.commit()


def test_market_page_primary_and_advanced_fields(app, client):
    _seed(app)
    login(client)
    html = client.get("/").get_data(as_text=True)
    assert 'id="weekFrom"' in html
    assert 'id="weekTo"' in html
    assert 'id="f-car-name"' in html
    assert 'id="f-search"' in html
    assert 'id="f-matrix"' in html
    assert 'id="f-advanced-toggle"' in html
    assert 'id="f-export"' in html
    assert 'id="advancedFilters"' in html
    assert 'id="f-maker"' in html
    assert 'id="f-model"' in html
    assert 'id="f-mdetail"' in html
    assert 'id="f-grade"' in html
    assert 'id="f-gdetail"' in html
    assert 'id="f-year"' in html
    assert 'id="f-fuel"' in html
    assert 'id="f-km"' in html
    assert 'id="f-awd"' not in html


def test_matrix_by_car_name_only(app, db):
    _seed(app)
    mat = market_query.matrix(
        car_name="CC", week_from="2026-W30", week_to="2026-W30",
    )
    assert mat["years"]
    assert mat["total_samples"] >= 1
    assert 2015 in mat["years"]


def test_matrix_by_maker_only(app, db):
    _seed(app)
    mat = market_query.matrix(
        maker="현대", week_from="2026-W30", week_to="2026-W30",
    )
    assert mat["total_samples"] >= 2
    assert 2020 in mat["years"]


def test_matrix_empty_without_criteria(app, db):
    _seed(app)
    mat = market_query.matrix(week_from="2026-W30", week_to="2026-W30")
    assert mat["years"] == []
    assert mat["total_samples"] == 0
