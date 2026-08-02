from flask import Blueprint, render_template, request
from flask_login import login_required

from app.services.weekly_briefing import build_briefing

briefing_bp = Blueprint("briefing", __name__)


@briefing_bp.route("/briefing")
@login_required
def index():
    period = (request.args.get("period") or "").strip() or None
    data = build_briefing(period)
    return render_template("briefing.html", data=data)
