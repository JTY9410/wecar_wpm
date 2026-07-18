from flask import Blueprint, jsonify, render_template, request, session
from flask_login import login_required

from app.services import market_query
from app.services.i18n_translate import load_pack

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
