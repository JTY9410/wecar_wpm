"""낙찰 상세 목록 컬럼 · 사고등급 알파벳 접두."""

from app.services import market_query
from app.services.accident import classify_accident
from app.services.excel_pipeline import process_weekly_upload
from tests.conftest import login
from tests.fixtures.make_fixture import build


def test_classify_accident_letter_prefix():
    assert classify_accident("무사고", 0, 0) == ("A-무사고", True)
    assert classify_accident("단순교환", 0, 0) == ("B-단순교환", False)
    assert classify_accident("사고", "본넷", 0) == ("C-외판교환", False)
    assert classify_accident("사고", 0, "도어(좌)") == ("D-외판판금", False)
    assert classify_accident("골격판금", "프론트펜더(좌)", 0) == ("E-골격판금", False)
    assert classify_accident(None, None, None) == ("A-무사고", True)


def test_samples_api_has_date_imported_and_letter_grade(app, db, tmp_path):
    with app.app_context():
        process_weekly_upload(
            build(str(tmp_path / "m.xlsx")), week_no="2026-W29", mode="reset",
        )
        data = market_query.samples(maker="현대", model_name="그랜저")
    assert data["ok"] is True
    assert data["count"] >= 1
    item = data["items"][0]
    assert item.get("auction_date")
    assert item.get("imported")
    assert item["accident_grade"].startswith(("A-", "B-", "C-", "D-", "E-", "F-"))


def test_market_samples_table_columns(client):
    login(client)
    html = client.get("/").get_data(as_text=True)
    start = html.index("market-samples-table")
    end = html.index("bpSamplesTableBody")
    thead = html[start:end]
    for label in ("경매일", "차량명", "연식", "주행구간", "사고등급", "낙찰가", "내수/수출"):
        assert label in thead, f"missing column: {label}"
    for gone in ("유종", "AWD", "XX교환", "W판금"):
        assert gone not in thead, f"unexpected column: {gone}"
    # 열 순서: 경매일이 차량명보다 앞
    assert thead.index("경매일") < thead.index("차량명")
    assert thead.index("낙찰가") < thead.index("내수/수출")
