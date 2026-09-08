import pytest

from app.extensions import db
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
    assert db.session.scalar(db.select(db.func.count()).select_from(AuctionRecord)) == 3
    assert db.session.scalar(db.select(db.func.count()).select_from(MarketSummary)) >= 1
    assert db.session.scalar(db.select(db.func.count()).select_from(VehiclePriceTable)) >= 1


def test_accident_free_flag(app, db, mini):
    process_weekly_upload(mini, week_no="2026-W29", mode="append")
    sonata = db.session.execute(db.select(AuctionRecord).where(AuctionRecord.car_name == "현대 쏘나타 디 엣지")).scalar_one_or_none()
    assert sonata.is_accident_free is True
    grandeur = db.session.execute(db.select(AuctionRecord).where(AuctionRecord.car_name == "현대 그랜저HG 300")).scalar_one_or_none()
    assert grandeur.is_accident_free is False  # 골격판금 + 교환/판금 존재


def test_overwrite_replaces_week(app, db, mini):
    process_weekly_upload(mini, week_no="2026-W29", mode="append")
    process_weekly_upload(mini, week_no="2026-W29", mode="overwrite")
    assert db.session.scalar(db.select(db.func.count()).select_from(AuctionRecord).where(AuctionRecord.week_no == "2026-W29")) == 3


def test_upload_stores_hierarchy_columns(app, db, mini):
    process_weekly_upload(mini, week_no="2026-W29", mode="append")
    row = db.session.execute(db.select(AuctionRecord).where(AuctionRecord.car_name == "현대 그랜저HG 300")).scalar_one_or_none()
    assert row.maker == "현대"
    assert row.model_name == "그랜저"
    assert row.mdetail_name == "그랜저HG"
    assert row.grade_name  # not full car_name dump
    assert "|" not in (row.car_code or "")
    assert len(row.car_code) == 16
    assert row.fuel
    assert row.awd
    assert row.is_accident_free is False


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


def test_upload_does_not_load_sheets_via_pandas(app, db, mini, monkeypatch):
    """xlsx는 chunksize가 없어 pandas 전체 로드를 쓰면 OOM 난다."""
    def boom(*_a, **_k):
        raise AssertionError("pd.read_excel / ExcelFile must not load whole sheets")

    import pandas as pd

    monkeypatch.setattr(pd, "read_excel", boom)
    monkeypatch.setattr(pd, "ExcelFile", boom)
    result = process_weekly_upload(mini, week_no="2026-W29", mode="append")
    assert result["rows_ok"] == 3
    assert db.session.scalar(db.select(db.func.count()).select_from(AuctionRecord)) == 3
    assert db.session.scalar(db.select(db.func.count()).select_from(VehiclePriceTable)) >= 1


def test_upload_uses_bulk_insert_not_orm_record_list(app, db, mini, monkeypatch):
    """배치 bulk_insert_mappings — AuctionRecord 인스턴스 전량 상주 금지."""
    orig = AuctionRecord.__init__
    n = {"orm": 0}

    def wrapped(self, *a, **k):
        n["orm"] += 1
        return orig(self, *a, **k)

    monkeypatch.setattr(AuctionRecord, "__init__", wrapped)
    batches = []
    real_bulk = db.session.bulk_insert_mappings

    def spy(mapper, mappings, **kwargs):
        batches.append(len(list(mappings)))
        return real_bulk(mapper, mappings, **kwargs)

    monkeypatch.setattr(db.session, "bulk_insert_mappings", spy)
    result = process_weekly_upload(mini, week_no="2026-W29", mode="append")
    assert result["rows_ok"] == 3
    assert n["orm"] == 0
    assert sum(batches) >= 3


def test_upload_does_not_construct_price_orm_rows(app, db, mini, monkeypatch):
    """시세표도 ORM 객체 리스트가 아니라 bulk mapping 으로만 적재한다."""
    orig = VehiclePriceTable.__init__
    n = {"orm": 0}

    def wrapped(self, *a, **k):
        n["orm"] += 1
        return orig(self, *a, **k)

    monkeypatch.setattr(VehiclePriceTable, "__init__", wrapped)
    process_weekly_upload(mini, week_no="2026-W29", mode="append")
    assert n["orm"] == 0
    assert db.session.scalar(db.select(db.func.count()).select_from(VehiclePriceTable)) >= 1
