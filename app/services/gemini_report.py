"""Tier 2 정성 소견 리포트 (PRD §5.6). Cache + daily rate limit + graceful fail."""
from datetime import date

from config import Config
from app.extensions import db
from app.models import GeminiReportCache, Listing, SyncLog
from app.services.llm_hub import LLMError, active_provider_name, get_provider

_daily_counter = {"date": None, "count": 0}


def _check_rate_limit():
    today = date.today().isoformat()
    if _daily_counter["date"] != today:
        _daily_counter["date"] = today
        _daily_counter["count"] = 0
    return _daily_counter["count"] < Config.RATE_LIMIT_DAILY


def _bump():
    _daily_counter["count"] += 1


def _build_prompt(listing):
    return (
        "다음 중고차 매물에 대한 정성적 소견 리포트를 한국어로 작성해줘. "
        "가격 수치를 직접 예측하지 말고 상태/시장 매력도/구매 시 유의점 위주로 서술해줘.\n"
        f"차명: {listing.car_name}\n연식: {listing.car_year}\n주행거리: {listing.car_km}km\n"
        f"수출/내수: {listing.imported}\n지역: {listing.sido}\n"
    )


def generate_report(car_no, force=False):
    """Returns dict(ok, cached, text|error). Graceful on any LLM failure."""
    listing = db.session.get(Listing, car_no)
    if listing is None:
        return {"ok": False, "error": "매물을 찾을 수 없습니다."}

    cached = db.session.get(GeminiReportCache, car_no)
    if cached and not force:
        return {"ok": True, "cached": True, "text": cached.report_text,
                "provider": active_provider_name()}

    if not _check_rate_limit():
        return {"ok": False, "error": "일일 리포트 요청 한도를 초과했습니다.", "graceful": True}

    try:
        provider = get_provider()
        text = provider.generate(_build_prompt(listing))
        _bump()
    except (LLMError, Exception) as exc:
        db.session.add(SyncLog(sync_type="LLM_REPORT", status="FAIL",
                               error_message=str(exc)))
        db.session.commit()
        return {"ok": False, "error": "임시 리포트 생성 불가능", "detail": str(exc),
                "graceful": True}

    if cached:
        cached.report_text = text
    else:
        cached = GeminiReportCache(car_no=car_no, report_text=text)
        db.session.add(cached)
    db.session.commit()
    return {"ok": True, "cached": False, "text": text, "provider": provider.name}
