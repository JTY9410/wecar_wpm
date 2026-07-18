"""주간 경매 엑셀 업로드 파이프라인 (PRD §4, §5, §8).

Sheet `경매전체데이터` → AuctionRecord (raw lake) → MarketSummary (grid aggregate).
Sheet `시세표_테이블` (header row 5) → VehiclePriceTable (car-code reference).
"""
import json
import re

import numpy as np
import pandas as pd

from app.extensions import db
from app.models import AuctionRecord, MarketSummary, VehiclePriceTable
from app.services.accident import is_accident_free
from app.services.awd_utils import normalize_awd
from app.services.car_code import build_car_code
from app.services.fuel_utils import normalize_fuel
from app.services.hierarchy import ensure_hierarchy
from app.services.mileage import calculate_mileage_bin

RAW_SHEET = "경매전체데이터"
PRICE_SHEET = "시세표_테이블"

# 실데이터 컬럼명 기준. PRD의 제조사/모델명 별칭 허용.
COLUMN_ALIASES = {
    "auction_date": ["경매일"],
    "maker": ["제작사", "제조사"],
    "kind": ["차종"],
    "model_name": ["모델명"],
    "car_name": ["차명"],
    "car_year": ["연식"],
    "car_km": ["주행거리"],
    "fuel": ["연료"],
    "start_price": ["시작가(만원)", "시작가"],
    "hope_price": ["희망가(만원)", "희망가"],
    "hammer_price": ["낙찰가"],
    "imported": ["내수수출구분", "내수/수출"],
    "accident_detail": ["사고'A' 상세", "사고A 상세"],
    "car_option": ["차량옵션"],
}
REQUIRED = ["auction_date", "maker", "car_name", "car_year", "car_km", "hammer_price", "imported"]


class ExcelValidationError(ValueError):
    pass


def _resolve_columns(df):
    """Map logical field → actual column name present in the sheet."""
    mapping = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                mapping[field] = alias
                break
    missing = [f for f in REQUIRED if f not in mapping]
    if missing:
        readable = {f: COLUMN_ALIASES[f][0] for f in missing}
        raise ExcelValidationError(f"필수 컬럼이 누락되었습니다: {list(readable.values())}")
    return mapping


def _find_col(df, needle):
    for c in df.columns:
        if needle in str(c):
            return c
    return None


def _to_int(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(float(re.sub(r"[^0-9.\-]", "", str(val)) or 0))
    except (TypeError, ValueError):
        return None


def _clean_km(val):
    i = _to_int(val)
    return i if i is not None else 0


def validate_excel_schema(df):
    _resolve_columns(df)
    return True


def parse_records(df, references, week_no):
    cols = _resolve_columns(df)
    xx_col = _find_col(df, "XX 교환")
    w_col = _find_col(df, "W 판금")
    records = []
    for _, row in df.iterrows():
        hammer = _to_int(row.get(cols["hammer_price"]))
        if hammer is None:
            continue
        maker = row.get(cols["maker"])
        kind = row.get(cols["kind"]) if cols.get("kind") else None
        model_name = row.get(cols["model_name"]) if cols.get("model_name") else kind
        car_name = row.get(cols["car_name"])
        fuel = normalize_fuel(row.get(cols["fuel"]) if cols.get("fuel") else None)
        imported = row.get(cols["imported"])
        car_year = _to_int(row.get(cols["car_year"]))
        km = _clean_km(row.get(cols["car_km"]))
        option = row.get(cols["car_option"]) if cols.get("car_option") else None
        awd = normalize_awd(str(car_name) if car_name is not None else None,
                            str(option) if option is not None else None, None)
        acc_detail = row.get(cols.get("accident_detail")) if cols.get("accident_detail") else None
        xx = row.get(xx_col) if xx_col else None
        w = row.get(w_col) if w_col else None
        acc_free = is_accident_free(acc_detail, xx, w)

        # 계층: 제조사 → 차종(모델) → 모델명(상세모델) → 등급(기본) → 차명(상세등급)
        hier = ensure_hierarchy(
            maker=str(maker) if maker is not None else None,
            model=str(kind) if kind is not None else str(model_name) if model_name is not None else None,
            mdetail=str(model_name) if model_name is not None else None,
            grade="기본",
            gdetail=str(car_name) if car_name is not None else None,
        )
        code = build_car_code(
            maker=hier["maker"], model=hier["model"], mdetail=hier["mdetail"],
            grade=hier["grade"], gdetail=hier["gdetail"],
            car_year=car_year, fuel=fuel, awd=awd,
            car_name=str(car_name) if car_name is not None else None,
            car_option=str(option) if option is not None else None,
        )
        rec = AuctionRecord(
            week_no=week_no,
            auction_date=str(row.get(cols["auction_date"])),
            maker=hier["maker"],
            model_name=hier["model"],
            mdetail_name=hier["mdetail"],
            grade_name=hier["grade"],
            gdetail_name=hier["gdetail"],
            car_name=str(car_name) if car_name is not None else None,
            car_year=car_year,
            car_km=km,
            fuel=fuel,
            awd=awd,
            imported=str(imported) if imported is not None else None,
            start_price=_to_int(row.get(cols["start_price"])) if cols.get("start_price") else None,
            hope_price=_to_int(row.get(cols["hope_price"])) if cols.get("hope_price") else None,
            hammer_price=hammer,
            accident_detail=str(acc_detail) if acc_detail is not None else None,
            xx_exchange=str(xx) if xx is not None else None,
            w_panel=str(w) if w is not None else None,
            is_accident_free=acc_free,
            maker_no=hier["maker_no"],
            model_no=hier["model_no"],
            mdetail_no=hier["mdetail_no"],
            grade_no=hier["grade_no"],
            gdetail_no=hier["gdetail_no"],
            car_code=code,
            km_bin=calculate_mileage_bin(km),
        )
        records.append(rec)
    db.session.flush()
    return records


def load_price_table(xls):
    """시세표_테이블 header at row 5 → long-form VehiclePriceTable rows."""
    if PRICE_SHEET not in xls.sheet_names:
        return []
    raw = pd.read_excel(xls, sheet_name=PRICE_SHEET, header=4)
    raw = raw.rename(columns=lambda c: str(c).strip())
    name_col = next((c for c in raw.columns if "차명" in c), None)
    if name_col is None:
        return []
    fuel_col = next((c for c in raw.columns if "연료" in c), None)
    imp_col = next((c for c in raw.columns if "내수" in c or "수출" in c), None)
    year_cols = [c for c in raw.columns if re.fullmatch(r"20\d{2}", str(c))]
    rows = []
    for _, r in raw.iterrows():
        name = r.get(name_col)
        if name is None or (isinstance(name, float) and pd.isna(name)):
            continue
        for yc in year_cols:
            price = _to_int(r.get(yc))
            if price is None or price == 0:
                continue
            rows.append(VehiclePriceTable(
                car_name=str(name).strip(),
                fuel=str(r.get(fuel_col)).strip() if fuel_col else None,
                imported=str(r.get(imp_col)).strip() if imp_col else None,
                car_year=int(yc),
                avg_price=price,
            ))
    return rows


def rebuild_market_summary(week_no):
    """Aggregate all AuctionRecord into MarketSummary; MoM vs previous week."""
    MarketSummary.query.delete()
    records = AuctionRecord.query.all()
    if not records:
        db.session.commit()
        return 0

    df = pd.DataFrame([{
        "car_code": r.car_code, "maker": r.maker, "model_name": r.model_name,
        "mdetail_name": r.mdetail_name, "grade_name": r.grade_name,
        "gdetail_name": r.gdetail_name, "car_name": r.car_name,
        "car_year": r.car_year, "fuel": r.fuel, "awd": r.awd,
        "imported": r.imported, "is_accident_free": r.is_accident_free,
        "km_bin": r.km_bin, "start_price": r.start_price,
        "hammer_price": r.hammer_price, "week_no": r.week_no,
    } for r in records])

    group_keys = ["car_code", "km_bin", "is_accident_free", "imported"]
    weekly = df.groupby(group_keys + ["week_no"], dropna=False).agg(
        hammer_avg=("hammer_price", "mean"),
    ).reset_index()

    latest = df.groupby(group_keys, dropna=False).agg(
        maker=("maker", "first"),
        model_name=("model_name", "first"),
        mdetail_name=("mdetail_name", "first"),
        grade_name=("grade_name", "first"),
        gdetail_name=("gdetail_name", "first"),
        car_name=("car_name", "first"),
        car_year=("car_year", "first"),
        fuel=("fuel", "first"),
        awd=("awd", "first"),
        start_avg=("start_price", "mean"),
        hammer_avg=("hammer_price", "mean"),
        sample_count=("hammer_price", "count"),
    ).reset_index()

    weeks_sorted = sorted([w for w in df["week_no"].dropna().unique()])
    prev_week = weeks_sorted[-2] if len(weeks_sorted) >= 2 else None
    prev_lookup = {}
    if prev_week is not None:
        pw = weekly[weekly["week_no"] == prev_week]
        for _, row in pw.iterrows():
            prev_lookup[tuple(row[k] for k in group_keys)] = row["hammer_avg"]

    count = 0
    for _, row in latest.iterrows():
        key = tuple(row[k] for k in group_keys)
        prev = prev_lookup.get(key)
        cur = row["hammer_avg"]
        mom = None
        if prev and prev != 0:
            mom = round((cur - prev) / prev * 100, 2)
        db.session.add(MarketSummary(
            car_code=row["car_code"], maker=row["maker"], model_name=row["model_name"],
            mdetail_name=row["mdetail_name"], grade_name=row["grade_name"],
            gdetail_name=row["gdetail_name"], car_name=row["car_name"],
            car_year=_safe_int(row["car_year"]), fuel=row["fuel"], awd=row["awd"],
            imported=row["imported"], is_accident_free=bool(row["is_accident_free"]),
            km_bin=row["km_bin"],
            start_avg=_safe_float(row["start_avg"]), hammer_avg=_safe_float(cur),
            mom_pct=mom, sample_count=int(row["sample_count"]), week_no=week_no,
            note=f"주간 집계 완료 ({week_no})",
        ))
        count += 1
    db.session.commit()
    return count


def _safe_int(v):
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_float(v):
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def process_weekly_upload(file_path, week_no, mode="append"):
    """Returns dict(rows_ok, records, summaries). Raises ExcelValidationError."""
    xls = pd.ExcelFile(file_path)
    if RAW_SHEET not in xls.sheet_names:
        raise ExcelValidationError(f"시트 '{RAW_SHEET}' 가 없습니다.")
    df = pd.read_excel(xls, sheet_name=RAW_SHEET)
    df = df.rename(columns=lambda c: str(c).strip())
    validate_excel_schema(df)

    if mode == "reset":
        AuctionRecord.query.delete()
        VehiclePriceTable.query.delete()
        db.session.commit()
    elif mode == "overwrite":
        AuctionRecord.query.filter_by(week_no=week_no).delete()
        db.session.commit()

    price_rows = load_price_table(xls)
    if price_rows and mode in ("reset", "overwrite"):
        VehiclePriceTable.query.delete()
    if price_rows:
        db.session.add_all(price_rows)
        db.session.commit()

    references = [
        {"car_name": r.car_name, "fuel": r.fuel, "imported": r.imported}
        for r in VehiclePriceTable.query.all()
    ]
    records = parse_records(df, references, week_no)
    db.session.add_all(records)
    db.session.commit()

    summaries = rebuild_market_summary(week_no)
    return {"rows_ok": len(records), "records": len(records), "summaries": summaries}
