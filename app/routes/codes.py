"""계층형 코드 캐스케이드 API (로그인 사용자용). car /api/codes 와 유사."""
from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.models import (
    MarketSummary, VehicleGrade, VehicleGradeDetail,
    VehicleMaker, VehicleModel, VehicleModelDetail,
)
from sqlalchemy import distinct

from app.extensions import db

codes_bp = Blueprint("codes", __name__, url_prefix="/api/codes")


@codes_bp.route("/makers")
@login_required
def makers():
    rows = VehicleMaker.query.order_by(VehicleMaker.maker_name).all()
    if rows:
        return jsonify([{"maker_no": r.maker_no, "maker_name": r.maker_name} for r in rows])
    # fallback to market summary names
    names = db.session.query(distinct(MarketSummary.maker)).filter(
        MarketSummary.maker.isnot(None)).order_by(MarketSummary.maker).all()
    return jsonify([{"maker_no": n[0], "maker_name": n[0]} for n in names])


@codes_bp.route("/models")
@login_required
def models():
    maker_no = request.args.get("maker_no") or request.args.get("maker")
    q = VehicleModel.query
    if maker_no:
        q = q.filter_by(maker_no=maker_no)
    rows = q.order_by(VehicleModel.model_name).all()
    if rows:
        return jsonify([{"model_no": r.model_no, "model_name": r.model_name} for r in rows])
    names = db.session.query(distinct(MarketSummary.model_name)).filter(
        MarketSummary.maker == maker_no, MarketSummary.model_name.isnot(None)
    ).order_by(MarketSummary.model_name).all()
    return jsonify([{"model_no": n[0], "model_name": n[0]} for n in names])


@codes_bp.route("/modeldetails")
@login_required
def modeldetails():
    model_no = request.args.get("model_no") or request.args.get("model")
    q = VehicleModelDetail.query
    if model_no:
        q = q.filter_by(model_no=model_no)
    rows = q.order_by(VehicleModelDetail.mdetail_name).all()
    if rows:
        return jsonify([{"mdetail_no": r.mdetail_no, "mdetail_name": r.mdetail_name} for r in rows])
    names = db.session.query(distinct(MarketSummary.mdetail_name)).filter(
        MarketSummary.model_name == model_no, MarketSummary.mdetail_name.isnot(None)
    ).order_by(MarketSummary.mdetail_name).all()
    return jsonify([{"mdetail_no": n[0], "mdetail_name": n[0]} for n in names])


@codes_bp.route("/grades")
@login_required
def grades():
    mdetail_no = request.args.get("mdetail_no") or request.args.get("mdetail")
    q = VehicleGrade.query
    if mdetail_no:
        q = q.filter_by(mdetail_no=mdetail_no)
    rows = q.order_by(VehicleGrade.grade_name).all()
    return jsonify([{"grade_no": r.grade_no, "grade_name": r.grade_name} for r in rows])


@codes_bp.route("/gradedetails")
@login_required
def gradedetails():
    grade_no = request.args.get("grade_no") or request.args.get("grade")
    q = VehicleGradeDetail.query
    if grade_no:
        q = q.filter_by(grade_no=grade_no)
    rows = q.order_by(VehicleGradeDetail.gdetail_name).all()
    return jsonify([{"gdetail_no": r.gdetail_no, "gdetail_name": r.gdetail_name} for r in rows])


@codes_bp.route("/years")
@login_required
def years():
    maker = request.args.get("maker")
    model = request.args.get("model")
    q = db.session.query(distinct(MarketSummary.car_year)).filter(
        MarketSummary.car_year.isnot(None))
    if maker:
        q = q.filter(MarketSummary.maker == maker)
    if model:
        q = q.filter(MarketSummary.model_name == model)
    return jsonify([r[0] for r in q.order_by(MarketSummary.car_year.desc()).all()])


@codes_bp.route("/fuels")
@login_required
def fuels():
    q = db.session.query(distinct(MarketSummary.fuel)).filter(MarketSummary.fuel.isnot(None))
    return jsonify([r[0] for r in q.order_by(MarketSummary.fuel).all()])


@codes_bp.route("/awd")
@login_required
def awd_list():
    return jsonify(["AWD", "2WD", "미확인"])
