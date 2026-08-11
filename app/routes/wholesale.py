"""car 소매시세 연동용 도매 시세 External API.

인증: Header `X-API-Key: <EXTERNAL_API_KEY>` 또는 `Authorization: Bearer <key>`
car1은 독립 운영하며, car는 이 API로 도매 시세(hammer_avg 등)를 조회한다.
"""
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models import (
    MarketSummary,
    VehicleCodeMapping,
    VehicleGrade,
    VehicleGradeDetail,
    VehicleMaker,
    VehicleModel,
    VehicleModelDetail,
)
from app.services.car_code import build_car_code
from app.services import api_keys as api_key_service
from app.services.code_resolve import resolve_vehicle_codes
from app.services import market_query

wholesale_bp = Blueprint("wholesale", __name__, url_prefix="/api/v1/wholesale")


def _resolve_kwargs_from_request():
    return {
        "maker_no": request.args.get("maker_no"),
        "model_no": request.args.get("model_no"),
        "mdetail_no": request.args.get("mdetail_no"),
        "grade_no": request.args.get("grade_no"),
        "gdetail_no": request.args.get("gdetail_no"),
        "maker": request.args.get("maker"),
        "model": request.args.get("model") or request.args.get("model_name"),
        "mdetail": request.args.get("mdetail") or request.args.get("mdetail_name"),
        "grade": request.args.get("grade") or request.args.get("grade_name"),
        "gdetail": request.args.get("gdetail") or request.args.get("gdetail_name"),
    }


def _resolved_response(resolved):
    return {
        "maker_no": resolved.get("maker_no"),
        "model_no": resolved.get("model_no"),
        "mdetail_no": resolved.get("mdetail_no"),
        "grade_no": resolved.get("grade_no"),
        "gdetail_no": resolved.get("gdetail_no"),
        "maker_name": resolved.get("maker_name"),
        "model_name": resolved.get("model_name"),
        "mdetail_name": resolved.get("mdetail_name"),
        "grade_name": resolved.get("grade_name"),
        "gdetail_name": resolved.get("gdetail_name"),
        "car2": resolved.get("car2") or {},
    }


def _apply_resolved_market_filters(q, resolved):
    if resolved.get("maker_name"):
        q = q.where(MarketSummary.maker == resolved["maker_name"])
    if resolved.get("model_name"):
        q = q.where(MarketSummary.model_name == resolved["model_name"])
    if resolved.get("mdetail_name"):
        q = q.where(MarketSummary.mdetail_name == resolved["mdetail_name"])
    if resolved.get("grade_name"):
        q = q.where(MarketSummary.grade_name == resolved["grade_name"])
    if resolved.get("gdetail_name"):
        q = q.where(MarketSummary.gdetail_name == resolved["gdetail_name"])
    return q


def _car2_codes_for_level(level, car1_codes):
    if not car1_codes:
        return {}
    rows = db.session.execute(
        db.select(VehicleCodeMapping.car1_code, VehicleCodeMapping.car2_code).where(
            VehicleCodeMapping.level == level,
            VehicleCodeMapping.car1_code.in_(car1_codes),
            VehicleCodeMapping.status == "confirmed",
        )
    ).all()
    return {car1: car2 for car1, car2 in rows}


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
    car_year = request.args.get("car_year", type=int)
    fuel = request.args.get("fuel")
    awd = request.args.get("awd")
    km_bin = request.args.get("km_bin")

    resolve_kw = _resolve_kwargs_from_request()
    has_hierarchy = any(resolve_kw.values())
    resolved = resolve_vehicle_codes(**resolve_kw) if has_hierarchy else {}

    q = db.select(MarketSummary).where(
        MarketSummary.hammer_avg.isnot(None),
        MarketSummary.hammer_avg > 0,
    )
    if car_code:
        q = q.where(MarketSummary.car_code == car_code)
    if has_hierarchy:
        q = _apply_resolved_market_filters(q, resolved)
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
    payload = {"ok": True, "count": len(items), "items": items}
    if has_hierarchy:
        payload["resolved"] = _resolved_response(resolved)
    return jsonify(payload)


@wholesale_bp.route("/lookup")
@require_api_key
def lookup():
    """계층 값으로 car_code 생성 + 매칭 시세 반환 (car 연동 헬퍼)."""
    resolve_kw = _resolve_kwargs_from_request()
    has_hierarchy = any(resolve_kw.values())
    resolved = resolve_vehicle_codes(**resolve_kw) if has_hierarchy else {}

    code = build_car_code(
        maker=resolved.get("maker_name") or request.args.get("maker"),
        model=resolved.get("model_name") or request.args.get("model"),
        mdetail=resolved.get("mdetail_name") or request.args.get("mdetail"),
        grade=resolved.get("grade_name") or request.args.get("grade"),
        gdetail=resolved.get("gdetail_name") or request.args.get("gdetail"),
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
        if has_hierarchy:
            q = _apply_resolved_market_filters(q, resolved)
        else:
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
    payload = {
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
    }
    if has_hierarchy:
        payload["resolved"] = _resolved_response(resolved)
    return jsonify(payload)


@wholesale_bp.route("/codes/makers")
@require_api_key
def codes_makers():
    rows = db.session.execute(db.select(VehicleMaker).order_by(VehicleMaker.maker_name)).scalars().all()
    car2 = _car2_codes_for_level("maker", [r.maker_no for r in rows])
    return jsonify({"ok": True, "items": [
        {
            "maker_no": r.maker_no,
            "maker_name": r.maker_name,
            **({"car2_code": car2[r.maker_no]} if r.maker_no in car2 else {}),
        }
        for r in rows
    ]})


@wholesale_bp.route("/codes/models")
@require_api_key
def codes_models():
    maker_no = request.args.get("maker_no")
    resolved = resolve_vehicle_codes(maker_no=maker_no) if maker_no else {}
    q = db.select(VehicleModel)
    if resolved.get("maker_no"):
        q = q.where(VehicleModel.maker_no == resolved["maker_no"])
    elif maker_no:
        q = q.where(VehicleModel.maker_no == maker_no)
    rows = db.session.execute(q.order_by(VehicleModel.model_name)).scalars().all()
    car2 = _car2_codes_for_level("model", [r.model_no for r in rows])
    return jsonify({"ok": True, "items": [
        {
            "model_no": r.model_no,
            "maker_no": r.maker_no,
            "model_name": r.model_name,
            **({"car2_code": car2[r.model_no]} if r.model_no in car2 else {}),
        }
        for r in rows
    ]})


@wholesale_bp.route("/codes/modeldetails")
@require_api_key
def codes_modeldetails():
    model_no = request.args.get("model_no")
    resolved = resolve_vehicle_codes(model_no=model_no) if model_no else {}
    q = db.select(VehicleModelDetail)
    if resolved.get("model_no"):
        q = q.where(VehicleModelDetail.model_no == resolved["model_no"])
    elif model_no:
        q = q.where(VehicleModelDetail.model_no == model_no)
    rows = db.session.execute(q.order_by(VehicleModelDetail.mdetail_name)).scalars().all()
    car2 = _car2_codes_for_level("mdetail", [r.mdetail_no for r in rows])
    return jsonify({"ok": True, "items": [
        {
            "mdetail_no": r.mdetail_no,
            "model_no": r.model_no,
            "mdetail_name": r.mdetail_name,
            **({"car2_code": car2[r.mdetail_no]} if r.mdetail_no in car2 else {}),
        }
        for r in rows
    ]})


@wholesale_bp.route("/codes/grades")
@require_api_key
def codes_grades():
    mdetail_no = request.args.get("mdetail_no")
    resolved = resolve_vehicle_codes(mdetail_no=mdetail_no) if mdetail_no else {}
    q = db.select(VehicleGrade)
    if resolved.get("mdetail_no"):
        q = q.where(VehicleGrade.mdetail_no == resolved["mdetail_no"])
    elif mdetail_no:
        q = q.where(VehicleGrade.mdetail_no == mdetail_no)
    rows = db.session.execute(q.order_by(VehicleGrade.grade_name)).scalars().all()
    car2 = _car2_codes_for_level("grade", [r.grade_no for r in rows])
    return jsonify({"ok": True, "items": [
        {
            "grade_no": r.grade_no,
            "mdetail_no": r.mdetail_no,
            "grade_name": r.grade_name,
            **({"car2_code": car2[r.grade_no]} if r.grade_no in car2 else {}),
        }
        for r in rows
    ]})


@wholesale_bp.route("/codes/gradedetails")
@require_api_key
def codes_gradedetails():
    grade_no = request.args.get("grade_no")
    resolved = resolve_vehicle_codes(grade_no=grade_no) if grade_no else {}
    q = db.select(VehicleGradeDetail)
    if resolved.get("grade_no"):
        q = q.where(VehicleGradeDetail.grade_no == resolved["grade_no"])
    elif grade_no:
        q = q.where(VehicleGradeDetail.grade_no == grade_no)
    rows = db.session.execute(q.order_by(VehicleGradeDetail.gdetail_name)).scalars().all()
    car2 = _car2_codes_for_level("gdetail", [r.gdetail_no for r in rows])
    return jsonify({"ok": True, "items": [
        {
            "gdetail_no": r.gdetail_no,
            "grade_no": r.grade_no,
            "gdetail_name": r.gdetail_name,
            **({"car2_code": car2[r.gdetail_no]} if r.gdetail_no in car2 else {}),
        }
        for r in rows
    ]})
