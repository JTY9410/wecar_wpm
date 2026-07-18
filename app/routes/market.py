from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app.services import market_query

market_bp = Blueprint("market", __name__)


@market_bp.route("/")
@login_required
def index():
    return render_template("market.html", makers=market_query.makers())


@market_bp.route("/api/cascade/models")
@login_required
def cascade_models():
    return jsonify(market_query.models(request.args.get("maker", "")))


@market_bp.route("/api/cascade/car_names")
@login_required
def cascade_car_names():
    return jsonify(market_query.mdetails(
        request.args.get("maker", ""), request.args.get("model_name", "")))


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
        car_year=request.args.get("car_year"),
        fuel=request.args.get("fuel"),
        awd=request.args.get("awd"),
    ))
