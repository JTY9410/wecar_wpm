from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app.services.weekly_briefing import build_briefing, fetch_trim_auction_details

briefing_bp = Blueprint("briefing", __name__)


@briefing_bp.route("/briefing")
@login_required
def index():
    period = (request.args.get("period") or "").strip() or None
    data = build_briefing(period)
    return render_template("briefing.html", data=data)


@briefing_bp.route("/briefing/api/details")
@login_required
def trim_details():
    """가격 특이사항 세부현황 — 금주/전주 낙찰 원장."""
    data = fetch_trim_auction_details(
        current_week=(request.args.get("current_week") or "").strip(),
        previous_week=(request.args.get("previous_week") or "").strip() or None,
        maker=(request.args.get("maker") or "").strip() or None,
        model_name=(request.args.get("model_name") or "").strip() or None,
        mdetail_name=(request.args.get("mdetail_name") or "").strip() or None,
        grade_name=(request.args.get("grade_name") or "").strip() or None,
        gdetail_name=(request.args.get("gdetail_name") or "").strip() or None,
    )
    status = 200 if data.get("ok") else 400
    return jsonify(data), status
