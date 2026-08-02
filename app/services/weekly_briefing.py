"""주간브리핑 — 전주 대비 금주 제조사+모델 낙찰가/표본수 변동 (도매)."""

from sqlalchemy import func

from app.extensions import db
from app.models import AuctionRecord

PRICE_THRESHOLD_PCT = 5.0
SURGE_THRESHOLD_PCT = 30.0


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
    rows = (
        db.session.query(
            AuctionRecord.maker,
            AuctionRecord.model_name,
            func.avg(AuctionRecord.hammer_price),
            func.count(AuctionRecord.id),
        )
        .filter(
            AuctionRecord.week_no == week_no,
            AuctionRecord.hammer_price.isnot(None),
            AuctionRecord.hammer_price > 0,
            AuctionRecord.maker.isnot(None),
            AuctionRecord.model_name.isnot(None),
        )
        .group_by(AuctionRecord.maker, AuctionRecord.model_name)
        .all()
    )
    return {
        (maker, model): {"avg_price": round(float(avg or 0)), "count": cnt}
        for maker, model, avg, cnt in rows
    }


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
        maker, model = key
        cur = cur_map.get(key)
        prev = prev_map.get(key)
        cur_price = cur["avg_price"] if cur else None
        prev_price = prev["avg_price"] if prev else None
        cur_count = cur["count"] if cur else 0
        prev_count = prev["count"] if prev else 0

        price_pct = None
        price_flag = False
        if cur_price is not None and prev_price:
            price_pct = round(((cur_price - prev_price) / prev_price) * 100, 1)
            price_flag = abs(price_pct) >= PRICE_THRESHOLD_PCT

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
            "maker_name": maker,
            "model_name": model,
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
        "surge_threshold": SURGE_THRESHOLD_PCT,
        "price_alert_on": True,
        "surge_alert_on": True,
    }
