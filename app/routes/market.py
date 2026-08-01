import logging

from flask import Blueprint, jsonify, render_template, request, session
from flask_login import login_required

from app.services import llm_hub, market_query
from app.services.i18n_translate import load_pack

logger = logging.getLogger(__name__)

market_bp = Blueprint("market", __name__)


def _lang():
    return session.get("lang") or request.args.get("lang") or "ko"


@market_bp.route("/")
@login_required
def index():
    return render_template(
        "market.html",
        makers=market_query.makers(),
        i18n=load_pack(_lang()),
        lang=_lang(),
    )


@market_bp.route("/api/cascade/models")
@login_required
def cascade_models():
    return jsonify(market_query.models(request.args.get("maker", "")))


@market_bp.route("/api/cascade/car_names")
@login_required
def cascade_car_names():
    return jsonify(market_query.mdetails(
        request.args.get("maker", ""), request.args.get("model_name", "")))


@market_bp.route("/api/cascade/grades")
@login_required
def cascade_grades():
    return jsonify(market_query.grades(
        request.args.get("maker", ""),
        request.args.get("model_name"),
        request.args.get("mdetail_name"),
    ))


@market_bp.route("/api/cascade/gdetails")
@login_required
def cascade_gdetails():
    return jsonify(market_query.gdetails(
        request.args.get("maker", ""),
        request.args.get("model_name"),
        request.args.get("mdetail_name"),
        request.args.get("grade_name"),
    ))


@market_bp.route("/api/cascade/years")
@login_required
def cascade_years():
    return jsonify(market_query.years(
        request.args.get("maker", ""), request.args.get("model_name"),
        request.args.get("car_name") or request.args.get("mdetail_name")))


@market_bp.route("/api/cascade/fuels")
@login_required
def cascade_fuels():
    return jsonify(market_query.fuels(request.args.get("maker")))


@market_bp.route("/api/grid")
@login_required
def grid():
    return jsonify(market_query.grid(
        maker=request.args.get("maker"),
        model_name=request.args.get("model_name"),
        mdetail_name=request.args.get("mdetail_name") or request.args.get("car_name"),
        grade_name=request.args.get("grade_name"),
        gdetail_name=request.args.get("gdetail_name"),
        car_year=request.args.get("car_year"),
        fuel=request.args.get("fuel"),
        awd=request.args.get("awd"),
        lang=_lang(),
    ))


@market_bp.route("/api/matrix")
@login_required
def matrix():
    return jsonify(market_query.matrix(
        maker=request.args.get("maker"),
        model_name=request.args.get("model_name"),
        mdetail_name=request.args.get("mdetail_name"),
        grade_name=request.args.get("grade_name"),
        gdetail_name=request.args.get("gdetail_name"),
        fuel=request.args.get("fuel"),
        awd=request.args.get("awd"),
        accident_free=request.args.get("accident_free"),
    ))


@market_bp.route("/api/price-forecast")
@login_required
def price_forecast():
    pack = load_pack(_lang())
    args = dict(
        maker=request.args.get("maker"),
        model_name=request.args.get("model_name"),
        mdetail_name=request.args.get("mdetail_name"),
        grade_name=request.args.get("grade_name"),
        gdetail_name=request.args.get("gdetail_name"),
        car_year=request.args.get("car_year"),
        fuel=request.args.get("fuel"),
        awd=request.args.get("awd"),
    )
    trend = market_query.price_trend(**args)
    calc = market_query.forecast_from_trend(trend)
    if not calc.get("ok"):
        return jsonify({"ok": False, "error": pack.get("forecast_empty")}), 200

    title = request.args.get("title") or " · ".join(
        v for v in [args["maker"], args["model_name"], args["gdetail_name"] or args["grade_name"]] if v
    )
    report_text = ""
    try:
        result = llm_hub.generate_price_forecast({
            "title": title, "trend": trend,
            "current_avg": calc["current_avg"], "expected_price": calc["expected_price"],
            "expected_pct": calc["expected_pct"],
        })
        report_text = result.get("text", "")
    except Exception:
        logger.exception("price forecast AI report failed")
        report_text = pack.get("report_fail", "")

    return jsonify({
        "ok": True,
        "trend": trend,
        "current_avg": calc["current_avg"],
        "expected_price": calc["expected_price"],
        "expected_pct": calc["expected_pct"],
        "basis": calc["basis"],
        "report": report_text,
        "note": pack.get("forecast_disclaimer"),
    })


@market_bp.route("/api/samples")
@login_required
def samples():
    return jsonify(market_query.samples(
        maker=request.args.get("maker"),
        model_name=request.args.get("model_name"),
        mdetail_name=request.args.get("mdetail_name"),
        grade_name=request.args.get("grade_name"),
        gdetail_name=request.args.get("gdetail_name"),
        car_year=request.args.get("car_year"),
        km_bin=request.args.get("km_bin"),
        fuel=request.args.get("fuel"),
        awd=request.args.get("awd"),
        accident_free=request.args.get("accident_free"),
        lang=_lang(),
    ))
