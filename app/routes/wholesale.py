"""car 소매시세 연동용 도매 시세 External API.

인증: Header `X-API-Key: <EXTERNAL_API_KEY>` 또는 `Authorization: Bearer <key>`
car1은 독립 운영하며, car는 이 API로 도매 시세(hammer_avg 등)를 조회한다.
"""
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app.models import MarketSummary, VehicleGrade, VehicleGradeDetail, VehicleMaker, VehicleModel, VehicleModelDetail
from app.services.car_code import build_car_code
from app.services import market_query

wholesale_bp = Blueprint("wholesale", __name__, url_prefix="/api/v1/wholesale")


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = (current_app.config.get("EXTERNAL_API_KEY") or "").strip()
        if not expected:
            return jsonify({"ok": False, "error": "EXTERNAL_API_KEY 미설정"}), 503
        provided = request.headers.get("X-API-Key", "")
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
        if provided != expected:
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

    q = MarketSummary.query.filter(
        MarketSummary.hammer_avg.isnot(None),
        MarketSummary.hammer_avg > 0,
    )
    if car_code:
        q = q.filter(MarketSummary.car_code == car_code)
    if maker:
        q = q.filter(MarketSummary.maker == maker)
    if model:
        q = q.filter(MarketSummary.model_name == model)
    if mdetail:
        q = q.filter(MarketSummary.mdetail_name == mdetail)
    if grade:
        q = q.filter(MarketSummary.grade_name == grade)
    if gdetail:
        q = q.filter(MarketSummary.gdetail_name == gdetail)
    if car_year:
        q = q.filter(MarketSummary.car_year == car_year)
    if fuel:
        q = q.filter(MarketSummary.fuel == fuel)
    if awd:
        q = q.filter(MarketSummary.awd == awd)
    if km_bin:
        q = q.filter(MarketSummary.km_bin == km_bin)

    limit = min(request.args.get("limit", 100, type=int), 500)
    rows = q.order_by(MarketSummary.car_year.desc()).limit(limit).all()
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
    q = MarketSummary.query.filter_by(car_code=code)
    # 해시 미일치 시 차원 컬럼으로 폴백 조회
    if q.count() == 0:
        q = MarketSummary.query
        if request.args.get("maker"):
            q = q.filter_by(maker=request.args.get("maker"))
        if request.args.get("model"):
            q = q.filter_by(model_name=request.args.get("model"))
        if request.args.get("mdetail"):
            q = q.filter_by(mdetail_name=request.args.get("mdetail"))
        if request.args.get("grade"):
            q = q.filter_by(grade_name=request.args.get("grade"))
        if request.args.get("gdetail"):
            q = q.filter_by(gdetail_name=request.args.get("gdetail"))
        if request.args.get("car_year", type=int):
            q = q.filter_by(car_year=request.args.get("car_year", type=int))
        if request.args.get("fuel"):
            q = q.filter_by(fuel=request.args.get("fuel"))
        if request.args.get("awd"):
            q = q.filter_by(awd=request.args.get("awd"))
    rows = q.limit(100).all()
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
    rows = VehicleMaker.query.order_by(VehicleMaker.maker_name).all()
    return jsonify({"ok": True, "items": [
        {"maker_no": r.maker_no, "maker_name": r.maker_name} for r in rows
    ]})


@wholesale_bp.route("/codes/models")
@require_api_key
def codes_models():
    maker_no = request.args.get("maker_no")
    q = VehicleModel.query
    if maker_no:
        q = q.filter_by(maker_no=maker_no)
    rows = q.order_by(VehicleModel.model_name).all()
    return jsonify({"ok": True, "items": [
        {"model_no": r.model_no, "maker_no": r.maker_no, "model_name": r.model_name} for r in rows
    ]})
