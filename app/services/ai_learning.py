"""AI학습진행도 — Tier1(자체 모델) vs Tier2(Gemini) 전환 현황 (도매)."""

from datetime import date
from pathlib import Path

from app.extensions import db
from app.models import (
    AiLearningMilestone,
    AuctionRecord,
    GeminiReportCache,
    SyncLog,
    UploadHistory,
)
from config import Config

PHASES = ["외부AI 의존", "전환중", "자체학습 완료"]


def get_progress_stats():
    retrain_logs = db.session.scalar(db.select(db.func.count()).select_from(SyncLog).where(
        SyncLog.sync_type.in_(["retrain", "ai_retrain", "model_retrain"])
    ))
    upload_ok = db.session.scalar(db.select(db.func.count()).select_from(UploadHistory).where(
        UploadHistory.status.in_(["SUCCESS", "ok", "done", "완료"])
    ))
    if upload_ok == 0:
        upload_ok = db.session.scalar(db.select(db.func.count()).select_from(UploadHistory))
    retrain_count = retrain_logs + upload_ok

    last_upload = db.session.execute(
        db.select(UploadHistory).order_by(UploadHistory.created_at.desc())
    ).scalar_one_or_none()
    last_sync = db.session.execute(
        db.select(SyncLog).order_by(SyncLog.created_at.desc())
    ).scalar_one_or_none()
    last_retrain_at = None
    if last_upload and last_upload.created_at:
        last_retrain_at = last_upload.created_at
    if last_sync and last_sync.created_at:
        if last_retrain_at is None or last_sync.created_at > last_retrain_at:
            last_retrain_at = last_sync.created_at

    training_samples = db.session.scalar(db.select(db.func.count()).select_from(AuctionRecord).where(
        AuctionRecord.hammer_price.isnot(None),
        AuctionRecord.hammer_price > 0,
    ))
    gemini_reports = db.session.scalar(db.select(db.func.count()).select_from(GeminiReportCache))
    # 도매: 정량은 자체 모델·통계, 정성은 Gemini 리포트 캐시
    local_analysis_count = training_samples
    gemini_analysis_count = gemini_reports
    total = local_analysis_count + gemini_analysis_count
    self_sufficiency_pct = (
        round((local_analysis_count / total) * 100, 1) if total else 0.0
    )

    return {
        "model_exists": Path(Config.MODEL_PATH).exists(),
        "retrain_count": retrain_count,
        "last_retrain_at": last_retrain_at,
        "training_samples": training_samples,
        "gemini_reports_cached": gemini_reports,
        "gemini_analysis_count": gemini_analysis_count,
        "local_analysis_count": local_analysis_count,
        "self_sufficiency_pct": self_sufficiency_pct,
    }


def list_milestones():
    return db.session.execute(db.select(AiLearningMilestone).order_by(
        AiLearningMilestone.recorded_date.desc(), AiLearningMilestone.id.desc()
    )).scalars().all()


def seed_default_milestone():
    if db.session.scalar(db.select(db.func.count()).select_from(AiLearningMilestone)) > 0:
        return
    db.session.add(
        AiLearningMilestone(
            recorded_date=date.today(),
            phase="전환중",
            title="2-Tier 하이브리드 AI 파이프라인 가동 (도매시세)",
            description=(
                "Tier 1(자체 scikit-learn)이 정량 가격 예측을 담당하고, "
                "Tier 2(Gemini)는 시세 리포트·예상가 요약 등 정성 분석에만 사용합니다. "
                "주간 엑셀 업로드·재학습으로 경매 표본이 쌓일수록 자체 학습 비중이 높아집니다."
            ),
        )
    )
    db.session.commit()
