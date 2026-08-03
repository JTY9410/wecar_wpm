"""주간브리핑 — 전주 대비 금주 세부등급(gdetail) 기준 낙찰가/표본수 변동."""

from sqlalchemy import func, or_

from app.extensions import db
from app.models import AuctionRecord

PRICE_THRESHOLD_PCT = 5.0
PRICE_ALERT_MIN_SAMPLES = 2  # 금주·전주 각각 최소 표본 (1건 노이즈 제외)
SURGE_THRESHOLD_PCT = 30.0
DETAIL_LIMIT = 200

# 세부등급 비교 키 (모델명만으로 묶지 않음)
_GROUP_KEYS = (
    AuctionRecord.maker,
    AuctionRecord.model_name,
    AuctionRecord.mdetail_name,
    AuctionRecord.grade_name,
    AuctionRecord.gdetail_name,
)


def _eq_or_null(column, value):
    """Match NULL as NULL (SQL NULL != NULL)."""
    if value in (None, ""):
        return column.is_(None)
    return column == value


def _filter_trim(q, *, maker, model_name, mdetail_name, grade_name, gdetail_name):
    return q.filter(
        _eq_or_null(AuctionRecord.maker, maker),
        _eq_or_null(AuctionRecord.model_name, model_name),
        _eq_or_null(AuctionRecord.mdetail_name, mdetail_name),
        _eq_or_null(AuctionRecord.grade_name, grade_name),
        _eq_or_null(AuctionRecord.gdetail_name, gdetail_name),
        AuctionRecord.hammer_price.isnot(None),
        AuctionRecord.hammer_price > 0,
    )


def _serialize_record(r: AuctionRecord) -> dict:
    return {
        "id": r.id,
        "week_no": r.week_no,
        "auction_date": r.auction_date,
        "car_name": r.car_name,
        "maker": r.maker,
        "model_name": r.model_name,
        "mdetail_name": r.mdetail_name,
        "grade_name": r.grade_name,
        "gdetail_name": r.gdetail_name,
        "car_year": r.car_year,
        "car_km": r.car_km,
        "km_bin": r.km_bin,
        "fuel": r.fuel,
        "awd": r.awd,
        "imported": r.imported,
        "start_price": r.start_price,
        "hope_price": r.hope_price,
        "hammer_price": r.hammer_price,
        "accident_detail": r.accident_detail,
        "is_accident_free": r.is_accident_free,
    }


def fetch_trim_auction_details(
    *,
    current_week: str,
    previous_week: str | None,
    maker: str | None,
    model_name: str | None = None,
    mdetail_name: str | None = None,
    grade_name: str | None = None,
    gdetail_name: str | None = None,
) -> dict:
    """금주·전주 낙찰 원장 (세부등급 키 일치)."""
    if not current_week or not maker:
        return {"ok": False, "error": "maker와 current_week가 필요합니다."}

    def _week_rows(week_no):
        if not week_no:
            return []
        q = AuctionRecord.query.filter(AuctionRecord.week_no == week_no)
        q = _filter_trim(
            q,
            maker=maker,
            model_name=model_name,
            mdetail_name=mdetail_name,
            grade_name=grade_name,
            gdetail_name=gdetail_name,
        )
        rows = q.order_by(
            AuctionRecord.hammer_price.desc(),
            AuctionRecord.id.desc(),
        ).limit(DETAIL_LIMIT).all()
        return [_serialize_record(r) for r in rows]

    current_items = _week_rows(current_week)
    previous_items = _week_rows(previous_week)
    trim = gdetail_name or grade_name or model_name or maker
    return {
        "ok": True,
        "current_week": current_week,
        "previous_week": previous_week,
        "trim_name": trim,
        "maker": maker,
        "model_name": model_name,
        "mdetail_name": mdetail_name,
        "grade_name": grade_name,
        "gdetail_name": gdetail_name,
        "current_items": current_items,
        "previous_items": previous_items,
        "current_count": len(current_items),
        "previous_count": len(previous_items),
    }


def _distinct_weeks(limit=12):
    rows = (
        db.session.query(AuctionRecord.week_no)
        .filter(AuctionRecord.week_no.isnot(None))
        .distinct()
        .order_by(AuctionRecord.week_no.desc())
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows if r[0]]


def _aggregate_week(week_no):
    """세부등급(gdetail) 단위로 주간 평균 낙찰가·표본수 집계.

    gdetail이 비어 있으면 grade를 세부 단위로 사용하되, 키에는 계층 전체를 포함해
    서로 다른 세부등급이 모델명만으로 합쳐지지 않게 한다.
    """
    rows = (
        db.session.query(
            AuctionRecord.maker,
            AuctionRecord.model_name,
            AuctionRecord.mdetail_name,
            AuctionRecord.grade_name,
            AuctionRecord.gdetail_name,
            func.avg(AuctionRecord.hammer_price),
            func.count(AuctionRecord.id),
        )
        .filter(
            AuctionRecord.week_no == week_no,
            AuctionRecord.hammer_price.isnot(None),
            AuctionRecord.hammer_price > 0,
            AuctionRecord.maker.isnot(None),
            or_(
                AuctionRecord.gdetail_name.isnot(None),
                AuctionRecord.grade_name.isnot(None),
            ),
        )
        .group_by(*_GROUP_KEYS)
        .all()
    )
    out = {}
    for maker, model, mdetail, grade, gdetail, avg, cnt in rows:
        key = (maker, model, mdetail, grade, gdetail)
        trim = gdetail or grade or model
        out[key] = {
            "maker_name": maker,
            "model_name": model,
            "mdetail_name": mdetail,
            "grade_name": grade,
            "gdetail_name": gdetail,
            "trim_name": trim,
            "avg_price": round(float(avg or 0)),
            "count": cnt,
        }
    return out


def build_briefing(week_no=None):
    weeks = _distinct_weeks()
    if not weeks:
        return {"available": False, "reason": "축적된 주간 경매 데이터가 없습니다."}

    current = week_no or weeks[0]
    if current not in weeks:
        return {"available": False, "reason": f"{current} 주차 데이터가 없습니다."}

    idx = weeks.index(current)
    previous = weeks[idx + 1] if idx + 1 < len(weeks) else None

    cur_map = _aggregate_week(current)
    prev_map = _aggregate_week(previous) if previous else {}

    rows = []
    for key in set(cur_map) | set(prev_map):
        cur = cur_map.get(key)
        prev = prev_map.get(key)
        meta = cur or prev
        cur_price = cur["avg_price"] if cur else None
        prev_price = prev["avg_price"] if prev else None
        cur_count = cur["count"] if cur else 0
        prev_count = prev["count"] if prev else 0

        price_pct = None
        price_flag = False
        if cur_price is not None and prev_price:
            price_pct = round(((cur_price - prev_price) / prev_price) * 100, 1)
            # 가격 특이사항: 전주대비 ±5% 이상이고 양쪽 표본이 충분할 때만
            price_flag = (
                abs(price_pct) >= PRICE_THRESHOLD_PCT
                and cur_count >= PRICE_ALERT_MIN_SAMPLES
                and prev_count >= PRICE_ALERT_MIN_SAMPLES
            )

        count_pct = None
        surge_flag = False
        new_entry = False
        if prev_count == 0 and cur_count > 0:
            new_entry = True
            surge_flag = True
        elif prev_count > 0:
            count_pct = round(((cur_count - prev_count) / prev_count) * 100, 1)
            surge_flag = count_pct >= SURGE_THRESHOLD_PCT

        rows.append({
            "maker_name": meta["maker_name"],
            "model_name": meta["model_name"],
            "mdetail_name": meta["mdetail_name"],
            "grade_name": meta["grade_name"],
            "gdetail_name": meta["gdetail_name"],
            "trim_name": meta["trim_name"],
            "cur_price": cur_price,
            "prev_price": prev_price,
            "price_pct": price_pct,
            "price_flag": price_flag,
            "cur_count": cur_count,
            "prev_count": prev_count,
            "count_pct": count_pct,
            "surge_flag": surge_flag,
            "new_entry": new_entry,
        })

    rows.sort(
        key=lambda r: (
            not (r["price_flag"] or r["surge_flag"]),
            -(abs(r["price_pct"]) if r["price_pct"] is not None else 0),
        )
    )

    total_cur = sum(r["cur_count"] for r in rows)
    total_prev = sum(r["prev_count"] for r in rows)
    total_pct = (
        round(((total_cur - total_prev) / total_prev) * 100, 1) if total_prev else None
    )

    return {
        "available": True,
        "current_period": current,
        "previous_period": previous,
        "periods": weeks,
        "rows": rows,
        "price_alerts": [r for r in rows if r["price_flag"]],
        "surge_alerts": [r for r in rows if r["surge_flag"]],
        "total_cur": total_cur,
        "total_prev": total_prev,
        "total_pct": total_pct,
        "price_threshold": PRICE_THRESHOLD_PCT,
        "price_alert_min_samples": PRICE_ALERT_MIN_SAMPLES,
        "surge_threshold": SURGE_THRESHOLD_PCT,
        "price_alert_on": True,
        "surge_alert_on": True,
        "compare_basis": "gdetail",
    }
