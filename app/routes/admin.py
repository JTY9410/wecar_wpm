import os
import re
import uuid
from datetime import datetime

from flask import (Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.decorators import admin_required
from app.extensions import db
from app.models import (
    AuctionRecord,
    LearnedGlossary,
    LLMConfig,
    SyncLog,
    TranslationCache,
    UploadHistory,
)
from app.services import google_translate, market_query, rag_store
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
    google_key = google_translate.resolve_api_key()
    return render_template(
        "admin_dashboard.html",
        history=history,
        logs=logs,
        llm_status=key_status(),
        rag_available=rag_store.is_available(),
        google_translate_status={
            "key_configured": bool(google_key),
            "key_hint": (google_key[:4] + "..." + google_key[-4:]) if len(google_key) >= 12 else ("설정됨" if google_key else "미설정"),
        },
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

    week_no = request.form.get("week_no") or _infer_week(file.filename)
    filename = secure_filename(file.filename)
    if not filename or "." not in filename:
        # Non-ASCII (e.g. Korean/Japanese) filenames collapse to just the
        # extension under secure_filename; fall back to a unique name so
        # uploads don't silently overwrite each other.
        filename = f"{uuid.uuid4().hex}{ext}"
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
    train = result.get("train") or {}
    message = (
        f"업로드 완료: {result['rows_ok']}행 · 시세 {result['summaries']}건 · "
        f"학습 {'성공' if train.get('trained') else 'SKIP'}"
    )
    if result.get("rag") and result["rag"] != "OK":
        message += f" · RAG {result['rag']}"
    return jsonify({"ok": True, "message": message, **result})


@admin_bp.route("/upload/clear", methods=["POST"])
@login_required
@admin_required
def upload_clear():
    from app.services.excel_pipeline import clear_all_auction_data
    result = clear_all_auction_data(clear_history=True)
    db.session.add(SyncLog(sync_type="UPLOAD_CLEAR", status="SUCCESS",
                           records_processed=result.get("deleted_records") or 0))
    db.session.commit()
    result["message"] = (
        f"전체 삭제 완료: 낙찰 {result['deleted_records']}건 · "
        f"시세 {result['deleted_summaries']}건 · 이력 {result['deleted_history']}건"
    )
    return jsonify(result)


@admin_bp.route("/upload/<int:history_id>/delete", methods=["POST"])
@login_required
@admin_required
def upload_delete(history_id):
    from app.services.excel_pipeline import delete_upload_by_history
    result = delete_upload_by_history(history_id)
    if not result.get("ok"):
        return jsonify(result), 404
    db.session.add(SyncLog(sync_type="UPLOAD_DELETE", status="SUCCESS",
                           records_processed=result.get("deleted_records") or 0,
                           error_message=f"week={result.get('week_no')}"))
    db.session.commit()
    result["message"] = (
        f"주차 {result.get('week_no')} 데이터 {result.get('deleted_records')}건 삭제 · "
        f"시세 재집계 {result.get('summaries')}건"
    )
    return jsonify(result)


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


@admin_bp.route("/translate/settings", methods=["POST"])
@login_required
@admin_required
def translate_settings():
    """Google 번역 API 키 저장 — 매물/차명 등 자유 텍스트 번역의 1차 엔진으로 사용."""
    api_key = request.form.get("api_key")
    clear_key = request.form.get("clear_key") == "1"
    if not clear_key and (api_key is None or not str(api_key).strip()):
        return jsonify({"ok": False, "error": "API 키를 입력하세요."}), 400
    google_translate.save_api_key(api_key=api_key, clear_key=clear_key)
    return jsonify({"ok": True, "message": "Google 번역 API 키가 저장되었습니다."})


@admin_bp.route("/translate/test", methods=["POST"])
@login_required
@admin_required
def translate_test():
    """Google 번역 API 연동 상태를 실제로 호출해 확인 (연결 테스트 버튼)."""
    result = google_translate.test_connection()
    db.session.add(SyncLog(
        sync_type="GOOGLE_TRANSLATE_TEST",
        status="SUCCESS" if result.get("ok") else "FAIL",
        records_processed=1 if result.get("ok") else 0,
        error_message=None if result.get("ok") else result.get("error"),
    ))
    db.session.commit()
    return jsonify(result), (200 if result.get("ok") else 400)


@admin_bp.route("/translations")
@login_required
@admin_required
def translations():
    """번역 캐시 관리 — 오역을 교정하고 검수/빈도 승격으로 자체 학습에 반영."""
    from app.services.i18n_translate import PROMOTE_THRESHOLD

    lang = request.args.get("lang", "en")
    if lang not in ("en", "ja"):
        lang = "en"
    q = (request.args.get("q") or "").strip()
    page = max(request.args.get("page", 1, type=int), 1)

    query = TranslationCache.query.filter_by(lang=lang)
    if q:
        query = query.filter(
            db.or_(
                TranslationCache.source_text.ilike(f"%{q}%"),
                TranslationCache.translated_text.ilike(f"%{q}%"),
            )
        )
    pagination = query.order_by(TranslationCache.reviewed.asc(), TranslationCache.id.desc()).paginate(
        page=page, per_page=30, error_out=False
    )
    glossary = (
        LearnedGlossary.query.filter_by(lang=lang)
        .order_by(LearnedGlossary.updated_at.desc())
        .limit(50)
        .all()
    )
    return render_template(
        "admin_translations.html",
        lang=lang,
        q=q,
        pagination=pagination,
        glossary=glossary,
        promote_threshold=PROMOTE_THRESHOLD,
        stats={
            "total": TranslationCache.query.filter_by(lang=lang).count(),
            "reviewed": TranslationCache.query.filter_by(lang=lang, reviewed=True).count(),
            "learned": LearnedGlossary.query.filter_by(lang=lang).count(),
        },
    )


@admin_bp.route("/translations/<int:entry_id>", methods=["POST"])
@login_required
@admin_required
def update_translation(entry_id):
    from app.services.i18n_translate import promote_to_glossary

    entry = TranslationCache.query.get_or_404(entry_id)
    action = request.form.get("action", "save")
    if action == "delete":
        db.session.delete(entry)
        db.session.commit()
        flash("번역 캐시 항목을 삭제했습니다. 다음 접속 시 다시 번역됩니다.", "success")
        return redirect(url_for("admin.translations", lang=entry.lang))

    new_text = request.form.get("translated_text", "").strip()
    if new_text:
        entry.translated_text = new_text
        entry.engine = "manual"
    entry.reviewed = request.form.get("reviewed") == "on"
    db.session.commit()
    if entry.reviewed:
        promote_to_glossary(
            entry.source_text, entry.lang, entry.translated_text,
            promoted_from="reviewed", hit_count=entry.hit_count or 0,
        )
    flash(
        "번역이 저장되었습니다."
        + (" (검수 완료 — 학습 용어집으로 승격되었습니다)" if entry.reviewed else ""),
        "success",
    )
    return redirect(url_for("admin.translations", lang=entry.lang, page=request.form.get("page", 1)))


@admin_bp.route("/translations/glossary/<int:entry_id>", methods=["POST"])
@login_required
@admin_required
def delete_learned_glossary(entry_id):
    entry = LearnedGlossary.query.get_or_404(entry_id)
    lang = entry.lang
    db.session.delete(entry)
    db.session.commit()
    flash("학습 용어집 항목을 삭제했습니다.", "success")
    return redirect(url_for("admin.translations", lang=lang))


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
