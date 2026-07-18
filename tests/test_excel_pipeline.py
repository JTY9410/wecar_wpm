import pytest

from app.models import AuctionRecord, MarketSummary, VehiclePriceTable
from app.services.excel_pipeline import (ExcelValidationError,
                                         process_weekly_upload,
                                         validate_excel_schema)
from tests.fixtures.make_fixture import build


@pytest.fixture()
def mini(tmp_path):
    return build(str(tmp_path / "mini.xlsx"))


def test_upload_appends_records(app, db, mini):
    result = process_weekly_upload(mini, week_no="2026-W29", mode="append")
    # 4 rows, 1 dropped (no hammer price) → 3 records
    assert result["rows_ok"] == 3
    assert AuctionRecord.query.count() == 3
    assert MarketSummary.query.count() >= 1
    assert VehiclePriceTable.query.count() >= 1


def test_accident_free_flag(app, db, mini):
    process_weekly_upload(mini, week_no="2026-W29", mode="append")
    sonata = AuctionRecord.query.filter_by(car_name="현대 쏘나타 디 엣지").first()
    assert sonata.is_accident_free is True
    grandeur = AuctionRecord.query.filter_by(car_name="현대 그랜저HG 300").first()
    assert grandeur.is_accident_free is False  # 골격판금 + 교환/판금 존재


def test_overwrite_replaces_week(app, db, mini):
    process_weekly_upload(mini, week_no="2026-W29", mode="append")
    process_weekly_upload(mini, week_no="2026-W29", mode="overwrite")
    assert AuctionRecord.query.filter_by(week_no="2026-W29").count() == 3


def test_missing_column_rejected(app, db, tmp_path):
    import openpyxl
    p = str(tmp_path / "bad.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "경매전체데이터"
    ws.append(["경매일", "제작사"])  # missing required columns
    ws.append(["2026-07-15", "현대"])
    wb.save(p)
    with pytest.raises(ExcelValidationError):
        process_weekly_upload(p, week_no="2026-W29", mode="append")
