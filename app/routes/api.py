from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services.gemini_report import generate_report
from app.services.hedonic_model import HedonicModel
from app.services.price_model import PriceModel

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/predict")
@login_required
def predict():
    model = PriceModel()
    price = model.predict(
        maker=request.args.get("maker"),
        car_year=_int(request.args.get("car_year")),
        car_km=_int(request.args.get("car_km")),
        imported=request.args.get("imported"),
    )
    if price is None:
        return jsonify({"ok": False, "error": "예측 모델이 아직 준비되지 않았습니다."}), 200
    return jsonify({"ok": True, "predicted_price": round(price, 1), "method": "random_forest"})


@api_bp.route("/predict/hedonic")
@login_required
def predict_hedonic():
    """헤도닉 분해 예측 — 속성별 기여도·잔차."""
    detail = HedonicModel().predict_detail(
        maker=request.args.get("maker"),
        car_year=_int(request.args.get("car_year")),
        car_km=_int(request.args.get("car_km")),
        fuel=request.args.get("fuel"),
        imported=request.args.get("imported"),
        is_accident_free=request.args.get("accident_free") in ("1", "true", "Y", "yes"),
        hammer_price=_float(request.args.get("hammer_price")),
    )
    if detail is None:
        return jsonify({"ok": False, "error": "헤도닉 모델이 아직 준비되지 않았습니다."}), 200
    return jsonify(detail)


@api_bp.route("/report/<car_no>", methods=["POST"])
@login_required
def report(car_no):
    result = generate_report(car_no, force=request.args.get("force") == "1")
    status = 200 if result.get("ok") else 200
    return jsonify(result), status


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None
