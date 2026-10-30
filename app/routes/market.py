import logging

from flask import Blueprint, jsonify, render_template, request, send_file, session
from flask_login import login_required

from app.services import car_info_api, diag_trim_resolve, llm_hub, market_query
from app.services.excel_export import export_full_grid_excel, export_grid_excel
from app.services.i18n_translate import load_pack

logger = logging.getLogger(__name__)

market_bp = Blueprint("market", __name__)


def _lang():
    return session.get("lang") or request.args.get("lang") or "ko"


@market_bp.route("/market/all")
@login_required
def full():
    lang = _lang()
    return render_template(
        "market_full.html",
        makers=market_query.makers(lang=lang),
        weeks=market_query.weeks(),
        i18n=load_pack(lang),
        lang=lang,
    )


@market_bp.route("/market/api/weeks")
@login_required
def api_weeks():
    return jsonify({"ok": True, "weeks": market_query.weeks()})


@market_bp.route("/market/api/full-grid")
@login_required
def full_grid():
    week_from = (request.args.get("week_from") or "").strip()
    week_to = (request.args.get("week_to") or "").strip()
    if not week_from or not week_to:
        return jsonify({"ok": False, "error": "경매차수 시작과 끝을 선택해주세요."}), 400
    return jsonify(market_query.full_grid(
        week_from=week_from,
        week_to=week_to,
        maker=request.args.get("maker"),
        model_name=request.args.get("model_name"),
        mdetail_name=request.args.get("mdetail_name") or request.args.get("car_name"),
        grade_name=request.args.get("grade_name"),
        gdetail_name=request.args.get("gdetail_name"),
        car_year=request.args.get("car_year"),
        fuel=request.args.get("fuel"),
        q=request.args.get("q"),
        lang=_lang(),
    ))


@market_bp.route("/")
@login_required
def index():
    lang = _lang()
    return render_template(
        "market.html",
        makers=market_query.makers(lang=lang),
        weeks=market_query.weeks(),
        km_bins=market_query.km_bins(lang=lang),
        i18n=load_pack(lang),
        lang=lang,
        car_info_configured=car_info_api.is_configured(),
    )


@market_bp.route("/api/lookup/plate", methods=["GET", "POST"])
@login_required
def lookup_plate():
    car_no = ""
    if request.method == "POST":
        if request.is_json and isinstance(request.json, dict):
            car_no = request.json.get("car_no") or ""
        else:
            car_no = request.form.get("car_no") or ""
    else:
        car_no = request.args.get("car_no") or ""
    car_no = str(car_no).strip()
    if not car_no:
        return jsonify({
            "ok": False,
            "error": "차량번호를 입력하세요.",
            "car_info_configured": car_info_api.is_configured(),
        }), 400
    result = diag_trim_resolve.lookup_plate_market(car_no, lang=_lang())
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@market_bp.route("/api/cascade/models")
@login_required
def cascade_models():
    return jsonify(market_query.models(request.args.get("maker", ""), lang=_lang()))


@market_bp.route("/api/cascade/car_names")
@login_required
def cascade_car_names():
    return jsonify(market_query.mdetails(
        request.args.get("maker", ""), request.args.get("model_name", ""),
        lang=_lang()))


@market_bp.route("/api/cascade/grades")
@login_required
def cascade_grades():
    return jsonify(market_query.grades(
        request.args.get("maker", ""),
        request.args.get("model_name"),
        request.args.get("mdetail_name"),
        lang=_lang(),
    ))


@market_bp.route("/api/cascade/gdetails")
@login_required
def cascade_gdetails():
    return jsonify(market_query.gdetails(
        request.args.get("maker", ""),
        request.args.get("model_name"),
        request.args.get("mdetail_name"),
        request.args.get("grade_name"),
        lang=_lang(),
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
    return jsonify(market_query.fuels(request.args.get("maker"), lang=_lang()))


@market_bp.route("/api/grid")
@login_required
def grid():
    week_from = (request.args.get("week_from") or "").strip()
    week_to = (request.args.get("week_to") or "").strip()
    if not week_from or not week_to:
        pack = load_pack(_lang())
        return jsonify({
            "ok": False,
            "error": pack.get("pick_weeks", "경매차수 시작과 끝을 선택하세요."),
        }), 400
    return jsonify(market_query.grid(
        maker=request.args.get("maker"),
        model_name=request.args.get("model_name"),
        mdetail_name=request.args.get("mdetail_name"),
        car_name=request.args.get("car_name") or request.args.get("q"),
        grade_name=request.args.get("grade_name"),
        gdetail_name=request.args.get("gdetail_name"),
        car_year=request.args.get("car_year"),
        fuel=request.args.get("fuel"),
        awd=request.args.get("awd"),
        km_bin=request.args.get("km_bin"),
        week_from=week_from,
        week_to=week_to,
        q=request.args.get("q"),
        lang=_lang(),
    ))


@market_bp.route("/api/cascade/km_bins")
@login_required
def cascade_km_bins():
    return jsonify(market_query.km_bins(
        week_from=request.args.get("week_from"),
        week_to=request.args.get("week_to"),
        maker=request.args.get("maker"),
        model_name=request.args.get("model_name"),
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
        car_name=request.args.get("car_name") or request.args.get("q"),
        car_year=request.args.get("car_year"),
        fuel=request.args.get("fuel"),
        awd=request.args.get("awd"),
        km_bin=request.args.get("km_bin"),
        accident_free=request.args.get("accident_free"),
        week_from=request.args.get("week_from"),
        week_to=request.args.get("week_to"),
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


@market_bp.route("/api/export/grid")
@login_required
def export_grid():
    week_from = (request.args.get("week_from") or "").strip()
    week_to = (request.args.get("week_to") or "").strip()
    if not week_from or not week_to:
        pack = load_pack(_lang())
        return jsonify({
            "ok": False,
            "error": pack.get("pick_weeks", "경매차수 시작과 끝을 선택하세요."),
        }), 400
    buf = export_grid_excel(request.args)
    return send_file(
        buf,
        as_attachment=True,
        download_name="wholesale_market_grid.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@market_bp.route("/market/api/export/full-grid")
@login_required
def export_full_grid():
    week_from = (request.args.get("week_from") or "").strip()
    week_to = (request.args.get("week_to") or "").strip()
    if not week_from or not week_to:
        return jsonify({"ok": False, "error": "경매차수 시작과 끝을 선택해주세요."}), 400
    buf = export_full_grid_excel(request.args)
    name = f"wholesale_full_market_{week_from}_{week_to}.xlsx".replace("/", "-")
    return send_file(
        buf,
        as_attachment=True,
        download_name=name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
