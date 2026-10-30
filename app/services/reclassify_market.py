"""기존 낙찰 데이터 사고등급·1만km 구간 재분류 후 시세 재집계."""
from __future__ import annotations

import logging

from app.extensions import db
from app.models import AuctionRecord, AnalysisLogic
from app.services.accident import classify_accident
from app.services.mileage import calculate_mileage_bin
from app.services.excel_pipeline import rebuild_market_summary
from config import Config

logger = logging.getLogger(__name__)

BATCH = 500


def ensure_km_bin_params():
    """분석로직 mileage.km_bin step을 1만km로 맞춘다(기존 row 덮어씀)."""
    row = db.session.execute(
        db.select(AnalysisLogic).where(AnalysisLogic.code == "mileage.km_bin")
    ).scalar_one_or_none()
    if row is None:
        return
    params = dict(row.params or {})
    params["step"] = Config.KM_BUCKET_STEP
    params["max"] = Config.KM_BUCKET_MAX
    row.params = params
    db.session.commit()


def reclassify_auction_records() -> dict:
    """auction_record 전건: accident_grade / is_accident_free / km_bin 재계산."""
    ensure_km_bin_params()
    total = db.session.scalar(db.select(db.func.count()).select_from(AuctionRecord)) or 0
    updated = 0
    offset = 0
    while offset < total:
        rows = db.session.execute(
            db.select(AuctionRecord).order_by(AuctionRecord.id).offset(offset).limit(BATCH)
        ).scalars().all()
        if not rows:
            break
        for r in rows:
            grade, free = classify_accident(r.accident_detail, r.xx_exchange, r.w_panel)
            new_bin = calculate_mileage_bin(r.car_km)
            if (
                r.accident_grade != grade
                or bool(r.is_accident_free) != bool(free)
                or r.km_bin != new_bin
            ):
                r.accident_grade = grade
                r.is_accident_free = free
                r.km_bin = new_bin
                updated += 1
        db.session.commit()
        offset += len(rows)

    latest = db.session.execute(
        db.select(AuctionRecord.week_no).where(AuctionRecord.week_no.isnot(None))
        .order_by(AuctionRecord.id.desc()).limit(1)
    ).scalar_one_or_none()
    summaries = rebuild_market_summary(latest) if latest else 0
    logger.info(
        "reclassify done: total=%s updated=%s summaries=%s week=%s",
        total, updated, summaries, latest,
    )
    return {
        "ok": True,
        "total": total,
        "updated": updated,
        "summaries": summaries,
        "week_no": latest,
    }
