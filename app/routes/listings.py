from flask import Blueprint, abort, render_template
from flask_login import login_required

from app.extensions import db
from app.models import GeminiReportCache, Listing

listings_bp = Blueprint("listings", __name__)


@listings_bp.route("/listings/<car_no>")
@login_required
def detail(car_no):
    listing = db.session.get(Listing, car_no)
    if listing is None:
        abort(404)
    report = db.session.get(GeminiReportCache, car_no)
    return render_template("listing_detail.html", listing=listing, report=report)
