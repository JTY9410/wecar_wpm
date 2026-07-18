import os
import re
from datetime import datetime

from flask import (Blueprint, current_app, jsonify, render_template, request)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.decorators import admin_required
from app.extensions import db
from app.models import AuctionRecord, LLMConfig, SyncLog, UploadHistory
from app.services import market_query, rag_store
from app.services.excel_pipeline import ExcelValidationError, process_weekly_upload
from app.services.llm_hub import (
    LLMError, generate_market_summary, key_status, save_provider_settings,
    set_active, test_provider,
)
from app.services.price_model import PriceModel
from app.services.sync_engine import sync_listings

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ALLOWED_EXT = {".xlsx", ".xls"}


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    history = UploadHistory.query.order_by(UploadHistory.created_at.desc()).limit(20).all()
    logs = SyncLog.query.order_by(SyncLog.created_at.desc()).limit(20).all()
    return render_template(
        "admin_dashboard.html",
        history=history,
        logs=logs,
        llm_status=key_status(),
        rag_available=rag_store.is_available(),
    )


def _infer_week(filename):
    m = re.search(r"(20\d{6})", filename)
    if m:
        d = datetime.strptime(m.group(1), "%Y%m%d")
        return f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"
    now = datetime.now()
    return f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"


@admin_bp.route("/upload", methods=["POST"])
@login_required
@admin_required
def upload():
    file = request.files.get("file")
    mode = request.form.get("mode", "append")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "파일이 없습니다."}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"ok": False, "error": "엑셀 파일(.xlsx/.xls)만 허용됩니다."}), 400

    filename = secure_filename(file.filename)
    week_no = request.form.get("week_no") or _infer_week(filename)
    dest = os.path.join(current_app.config["EXCEL_UPLOAD_PATH"], filename)
    os.makedirs(current_app.config["EXCEL_UPLOAD_PATH"], exist_ok=True)
    file.save(dest)

    try:
        result = process_weekly_upload(dest, week_no=week_no, mode=mode)
    except ExcelValidationError as exc:
        db.session.add(UploadHistory(filename=filename, week_no=week_no, mode=mode,
                                     status="FAIL", rows_ok=0,
                                     operator=current_user.username))
        db.session.add(SyncLog(sync_type="WEEKLY_EXCEL_UPLOAD", status="FAIL",
                               error_message=str(exc)))
        db.session.commit()
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        db.session.add(UploadHistory(filename=filename, week_no=week_no, mode=mode,
                                     status="FAIL", rows_ok=0,
                                     operator=current_user.username))
        db.session.add(SyncLog(sync_type="WEEKLY_EXCEL_UPLOAD", status="FAIL",
                               error_message=str(exc)))
        db.session.commit()
        return jsonify({"ok": False, "error": f"업로드 처리 실패: {exc}"}), 500

    db.session.add(UploadHistory(filename=filename, week_no=week_no, mode=mode,
                                 status="SUCCESS", rows_ok=result["rows_ok"],
                                 operator=current_user.username))
    db.session.add(SyncLog(sync_type="WEEKLY_EXCEL_UPLOAD", status="SUCCESS",
                           records_processed=result["rows_ok"]))
    db.session.commit()

    result["train"] = PriceModel().train()
    rag_status = rag_store.embed_records(
        AuctionRecord.query.filter_by(week_no=week_no).all()
    )
    result["rag"] = rag_status.get("status")
    return jsonify({"ok": True, **result})


@admin_bp.route("/sync", methods=["POST"])
@admin_bp.route("/sync/trigger", methods=["POST"])
@login_required
@admin_required
def sync():
    result = sync_listings(with_images=request.form.get("images") == "1")
    if result.get("status") == "SUCCESS":
        result["train"] = PriceModel().train()
    return jsonify(result)


@admin_bp.route("/retrain", methods=["POST"])
@login_required
@admin_required
def retrain():
    return jsonify(PriceModel().train())


@admin_bp.route("/llm", methods=["POST"])
@login_required
@admin_required
def switch_llm():
    provider = request.form.get("provider", "")
    try:
        set_active(provider)
    except LLMError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "active": provider, "status": key_status()})


@admin_bp.route("/llm/settings", methods=["POST"])
@login_required
@admin_required
def llm_settings():
    provider = request.form.get("provider", "").strip()
    model_name = request.form.get("model_name")
    api_key = request.form.get("api_key")
    clear_key = request.form.get("clear_key") == "1"
    if not clear_key and (api_key is None or not str(api_key).strip()) and model_name is None:
        return jsonify({"ok": False, "error": "API 키 또는 모델명을 입력하세요."}), 400
    if not clear_key and api_key is not None and not str(api_key).strip():
        return jsonify({"ok": False, "error": "API 키를 입력하세요."}), 400
    try:
        save_provider_settings(
            provider,
            api_key=api_key if api_key not in (None, "") else None,
            model_name=model_name,
            clear_key=clear_key,
        )
    except LLMError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "message": f"{provider} 설정이 저장되었습니다.",
                    "status": key_status()})


@admin_bp.route("/llm/test", methods=["POST"])
@login_required
@admin_required
def llm_test():
    provider = request.form.get("provider") or None
    result = test_provider(provider)
    db.session.add(SyncLog(
        sync_type="LLM_TEST",
        status="SUCCESS" if result.get("ok") else "FAIL",
        records_processed=1 if result.get("ok") else 0,
        error_message=None if result.get("ok") else result.get("error"),
    ))
    db.session.commit()
    return jsonify(result), (200 if result.get("ok") else 400)


@admin_bp.route("/llm/summary", methods=["POST"])
@login_required
@admin_required
def llm_summary():
    rows = market_query.grid()[:40]
    if not rows:
        return jsonify({"ok": False, "error": "시세 집계 데이터가 없습니다. 엑셀을 먼저 업로드하세요."}), 400
    try:
        result = generate_market_summary(rows)
    except LLMError as exc:
        db.session.add(SyncLog(sync_type="LLM_SUMMARY", status="FAIL",
                               error_message=str(exc)))
        db.session.commit()
        return jsonify({"ok": False, "error": "임시 리포트 생성 불가능",
                        "detail": str(exc), "graceful": True}), 200
    except Exception as exc:
        db.session.add(SyncLog(sync_type="LLM_SUMMARY", status="FAIL",
                               error_message=str(exc)))
        db.session.commit()
        return jsonify({"ok": False, "error": "임시 리포트 생성 불가능",
                        "detail": str(exc), "graceful": True}), 200
    db.session.add(SyncLog(sync_type="LLM_SUMMARY", status="SUCCESS",
                           records_processed=len(rows)))
    db.session.commit()
    return jsonify(result)


@admin_bp.route("/llm/status")
@login_required
@admin_required
def llm_status():
    return jsonify({"ok": True, "status": key_status()})


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    from app.models import User
    rows = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=rows)


@admin_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def users_approve(user_id):
    from app.models import User
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"ok": False, "error": "사용자를 찾을 수 없습니다."}), 404
    if user.id == current_user.id:
        return jsonify({"ok": False, "error": "본인 계정은 변경할 수 없습니다."}), 400
    user.is_approved = True
    db.session.commit()
    return jsonify({"ok": True, "user_id": user.id, "is_approved": True})


@admin_bp.route("/users/<int:user_id>/revoke", methods=["POST"])
@login_required
@admin_required
def users_revoke(user_id):
    from app.models import User
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"ok": False, "error": "사용자를 찾을 수 없습니다."}), 404
    if user.id == current_user.id:
        return jsonify({"ok": False, "error": "본인 계정은 변경할 수 없습니다."}), 400
    user.is_approved = False
    db.session.commit()
    return jsonify({"ok": True, "user_id": user.id, "is_approved": False})
