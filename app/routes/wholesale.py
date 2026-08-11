"""car 소매시세 연동용 도매 시세 External API.

인증: Header `X-API-Key: <EXTERNAL_API_KEY>` 또는 `Authorization: Bearer <key>`
car1은 독립 운영하며, car는 이 API로 도매 시세(hammer_avg 등)를 조회한다.
"""
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models import MarketSummary, VehicleGrade, VehicleGradeDetail, VehicleMaker, VehicleModel, VehicleModelDetail
from app.services.car_code import build_car_code
from app.services import api_keys as api_key_service
from app.services import market_query

wholesale_bp = Blueprint("wholesale", __name__, url_prefix="/api/v1/wholesale")


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not api_key_service.has_any_auth_configured():
            return jsonify({"ok": False, "error": "API key not configured"}), 503
        provided = request.headers.get("X-API-Key", "")
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
        if api_key_service.verify_api_key(provided) is None:
            return jsonify({"ok": False, "error": "invalid api key"}), 401
        return fn(*args, **kwargs)
    return wrapper


@wholesale_bp.route("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "wecarwpm-wholesale",
        "app": current_app.config["APP_NAME"],
        "integration_mode": current_app.config.get("INTEGRATION_MODE", "standalone"),
    })


@wholesale_bp.route("/prices")
@require_api_key
def prices():
    """도매 시세 조회. car_code 또는 계층 파라미터로 필터."""
    car_code = request.args.get("car_code")
    maker = request.args.get("maker")
    model = request.args.get("model") or request.args.get("model_name")
    mdetail = request.args.get("mdetail") or request.args.get("mdetail_name")
    grade = request.args.get("grade") or request.args.get("grade_name")
    gdetail = request.args.get("gdetail") or request.args.get("gdetail_name")
    car_year = request.args.get("car_year", type=int)
    fuel = request.args.get("fuel")
    awd = request.args.get("awd")
    km_bin = request.args.get("km_bin")

    q = db.select(MarketSummary).where(
        MarketSummary.hammer_avg.isnot(None),
        MarketSummary.hammer_avg > 0,
    )
    if car_code:
        q = q.where(MarketSummary.car_code == car_code)
    if maker:
        q = q.where(MarketSummary.maker == maker)
    if model:
        q = q.where(MarketSummary.model_name == model)
    if mdetail:
        q = q.where(MarketSummary.mdetail_name == mdetail)
    if grade:
        q = q.where(MarketSummary.grade_name == grade)
    if gdetail:
        q = q.where(MarketSummary.gdetail_name == gdetail)
    if car_year:
        q = q.where(MarketSummary.car_year == car_year)
    if fuel:
        q = q.where(MarketSummary.fuel == fuel)
    if awd:
        q = q.where(MarketSummary.awd == awd)
    if km_bin:
        q = q.where(MarketSummary.km_bin == km_bin)

    limit = min(request.args.get("limit", 100, type=int), 500)
    rows = db.session.execute(q.order_by(MarketSummary.car_year.desc()).limit(limit)).scalars().all()
    items = [{
        "car_code": r.car_code,
        "maker": r.maker,
        "model": r.model_name,
        "mdetail": r.mdetail_name,
        "grade": r.grade_name,
        "gdetail": r.gdetail_name,
        "car_year": r.car_year,
        "fuel": r.fuel,
        "awd": r.awd,
        "imported": r.imported,
        "is_accident_free": r.is_accident_free,
        "km_bin": r.km_bin,
        "start_avg": r.start_avg,
        "hammer_avg": r.hammer_avg,
        "wow_pct": r.mom_pct,  # 전주대비(%) — DB 컬럼명 mom_pct 유지
        "mom_pct": r.mom_pct,  # backward-compat alias
        "sample_count": r.sample_count,
        "week_no": r.week_no,
        "note": r.note,
    } for r in rows]
    return jsonify({"ok": True, "count": len(items), "items": items})


@wholesale_bp.route("/lookup")
@require_api_key
def lookup():
    """계층 값으로 car_code 생성 + 매칭 시세 반환 (car 연동 헬퍼)."""
    code = build_car_code(
        maker=request.args.get("maker"),
        model=request.args.get("model"),
        mdetail=request.args.get("mdetail"),
        grade=request.args.get("grade"),
        gdetail=request.args.get("gdetail"),
        car_year=request.args.get("car_year", type=int),
        fuel=request.args.get("fuel"),
        awd=request.args.get("awd"),
        accident_free=(
            True if request.args.get("accident_free") == "1"
            else False if request.args.get("accident_free") == "0"
            else None
        ),
    )
    q = db.select(MarketSummary).where(MarketSummary.car_code == code)
    # 해시 미일치 시 차원 컬럼으로 폴백 조회
    if db.session.scalar(db.select(db.func.count()).select_from(MarketSummary).where(MarketSummary.car_code == code)) == 0:
        q = db.select(MarketSummary)
        if request.args.get("maker"):
            q = q.where(MarketSummary.maker == request.args.get("maker"))
        if request.args.get("model"):
            q = q.where(MarketSummary.model_name == request.args.get("model"))
        if request.args.get("mdetail"):
            q = q.where(MarketSummary.mdetail_name == request.args.get("mdetail"))
        if request.args.get("grade"):
            q = q.where(MarketSummary.grade_name == request.args.get("grade"))
        if request.args.get("gdetail"):
            q = q.where(MarketSummary.gdetail_name == request.args.get("gdetail"))
        if request.args.get("car_year", type=int):
            q = q.where(MarketSummary.car_year == request.args.get("car_year", type=int))
        if request.args.get("fuel"):
            q = q.where(MarketSummary.fuel == request.args.get("fuel"))
        if request.args.get("awd"):
            q = q.where(MarketSummary.awd == request.args.get("awd"))
    rows = db.session.execute(q.limit(100)).scalars().all()
    return jsonify({
        "ok": True,
        "car_code": code,
        "count": len(rows),
        "items": [{
            "maker": r.maker, "model": r.model_name, "mdetail": r.mdetail_name,
            "grade": r.grade_name, "gdetail": r.gdetail_name,
            "car_year": r.car_year, "fuel": r.fuel, "awd": r.awd,
            "is_accident_free": r.is_accident_free,
            "km_bin": r.km_bin, "hammer_avg": r.hammer_avg,
            "start_avg": r.start_avg, "sample_count": r.sample_count,
            "wow_pct": r.mom_pct, "mom_pct": r.mom_pct, "imported": r.imported,
            "car_code": r.car_code,
        } for r in rows],
    })


@wholesale_bp.route("/codes/makers")
@require_api_key
def codes_makers():
    rows = db.session.execute(db.select(VehicleMaker).order_by(VehicleMaker.maker_name)).scalars().all()
    return jsonify({"ok": True, "items": [
        {"maker_no": r.maker_no, "maker_name": r.maker_name} for r in rows
    ]})


@wholesale_bp.route("/codes/models")
@require_api_key
def codes_models():
    maker_no = request.args.get("maker_no")
    q = db.select(VehicleModel)
    if maker_no:
        q = q.where(VehicleModel.maker_no == maker_no)
    rows = db.session.execute(q.order_by(VehicleModel.model_name)).scalars().all()
    return jsonify({"ok": True, "items": [
        {"model_no": r.model_no, "maker_no": r.maker_no, "model_name": r.model_name} for r in rows
    ]})
