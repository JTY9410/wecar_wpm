import os
import re
import uuid
import json
from datetime import date, datetime

from flask import (Blueprint, current_app, flash, jsonify, make_response, redirect, render_template, request, url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.decorators import admin_required
from app.extensions import db
from app.models import (
    AiLearningMilestone,
    ApiKey,
    AnalysisLogic,
    AuctionRecord,
    LearnedGlossary,
    LLMConfig,
    SyncLog,
    TranslationCache,
    UploadHistory,
    VehicleCodeMapping,
)
from app.services import api_keys as api_key_service
from app.services import analysis_logic as analysis_logic_service
from app.services import code_mapping_sync
from app.services.ai_learning import get_progress_stats, list_milestones, seed_default_milestone
from app.services import google_translate, market_query, rag_store
from app.services.excel_pipeline import ExcelValidationError, process_weekly_upload
from app.services.llm_hub import (
    LLMError, generate_market_summary, key_status, save_provider_settings,
    set_active, test_provider,
)
from app.services.price_model import PriceModel
from app.services.hedonic_model import HedonicModel
from app.services.sync_engine import sync_listings

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ALLOWED_EXT = {".xlsx", ".xls"}


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    history = db.session.execute(db.select(UploadHistory).order_by(UploadHistory.created_at.desc()).limit(20)).scalars().all()
    logs = db.session.execute(db.select(SyncLog).order_by(SyncLog.created_at.desc()).limit(20)).scalars().all()
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
    result["hedonic"] = HedonicModel().train()
    rag_status = rag_store.embed_records(
        db.session.execute(db.select(AuctionRecord).where(AuctionRecord.week_no == week_no)).scalars().all()
    )
    result["rag"] = rag_status.get("status")
    train = result.get("train") or {}
    hedonic = result.get("hedonic") or {}
    message = (
        f"업로드 완료: {result['rows_ok']}행 · 시세 {result['summaries']}건 · "
        f"학습 {'성공' if train.get('trained') else 'SKIP'} · "
        f"헤도닉 {'성공' if hedonic.get('trained') else 'SKIP'}"
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
        result["hedonic"] = HedonicModel().train()
    return jsonify(result)


@admin_bp.route("/retrain", methods=["POST"])
@login_required
@admin_required
def retrain():
    rf = PriceModel().train()
    hedonic = HedonicModel().train()
    return jsonify({"ok": True, "train": rf, "hedonic": hedonic})


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

    query = db.select(TranslationCache).where(TranslationCache.lang == lang)
    if q:
        query = query.where(
            db.or_(
                TranslationCache.source_text.ilike(f"%{q}%"),
                TranslationCache.translated_text.ilike(f"%{q}%"),
            )
        )
    pagination = db.paginate(
        query.order_by(TranslationCache.reviewed.asc(), TranslationCache.id.desc()),
        page=page, per_page=30, error_out=False
    )
    glossary = db.session.execute(
        db.select(LearnedGlossary)
        .where(LearnedGlossary.lang == lang)
        .order_by(LearnedGlossary.updated_at.desc())
        .limit(50)
    ).scalars().all()
    return render_template(
        "admin_translations.html",
        lang=lang,
        q=q,
        pagination=pagination,
        glossary=glossary,
        promote_threshold=PROMOTE_THRESHOLD,
        stats={
            "total": db.session.scalar(db.select(db.func.count()).select_from(TranslationCache).where(TranslationCache.lang == lang)),
            "reviewed": db.session.scalar(db.select(db.func.count()).select_from(TranslationCache).where(TranslationCache.lang == lang, TranslationCache.reviewed == True)),
            "learned": db.session.scalar(db.select(db.func.count()).select_from(LearnedGlossary).where(LearnedGlossary.lang == lang)),
        },
    )


@admin_bp.route("/translations/<int:entry_id>", methods=["POST"])
@login_required
@admin_required
def update_translation(entry_id):
    from app.services.i18n_translate import promote_to_glossary

    entry = db.get_or_404(TranslationCache, entry_id)
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
    entry = db.get_or_404(LearnedGlossary, entry_id)
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
    rows = db.session.execute(db.select(User).order_by(User.created_at.desc())).scalars().all()
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


@admin_bp.route("/ai-learning")
@login_required
@admin_required
def ai_learning():
    seed_default_milestone()
    return render_template(
        "admin_ai_learning.html",
        stats=get_progress_stats(),
        milestones=list_milestones(),
        phases=["외부AI 의존", "전환중", "자체학습 완료"],
    )


@admin_bp.route("/ai-learning", methods=["POST"])
@login_required
@admin_required
def create_milestone():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "제목을 입력해주세요."}), 400
    row = AiLearningMilestone(
        recorded_date=date.today(),
        phase=(data.get("phase") or "전환중").strip(),
        title=title,
        description=(data.get("description") or "").strip(),
        created_by=current_user.id,
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"success": True, "id": row.id})


@admin_bp.route("/ai-learning/<int:row_id>", methods=["POST"])
@login_required
@admin_required
def update_milestone(row_id):
    row = db.get_or_404(AiLearningMilestone, row_id)
    data = request.get_json(silent=True) or {}
    row.title = (data.get("title") or row.title).strip()
    row.phase = (data.get("phase") or row.phase).strip()
    row.description = (data.get("description") or "").strip()
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/ai-learning/<int:row_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_milestone(row_id):
    row = db.get_or_404(AiLearningMilestone, row_id)
    db.session.delete(row)
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/developer")
@login_required
@admin_required
def developer():
    tab = request.args.get("tab", "docs")
    if tab not in ("docs", "keys", "mapping"):
        tab = "docs"

    keys = []
    mappings = []
    status_filter = request.args.get("status", "")
    level_filter = request.args.get("level", "")

    if tab == "keys":
        keys = db.session.execute(
            db.select(ApiKey).order_by(ApiKey.created_at.desc())
        ).scalars().all()
    elif tab == "mapping":
        q = db.select(VehicleCodeMapping).order_by(VehicleCodeMapping.updated_at.desc())
        if status_filter in ("candidate", "confirmed", "rejected"):
            q = q.where(VehicleCodeMapping.status == status_filter)
        if level_filter in ("maker", "model", "mdetail", "grade", "gdetail"):
            q = q.where(VehicleCodeMapping.level == level_filter)
        mappings = db.session.execute(q.limit(200)).scalars().all()

    return render_template(
        "admin_developer.html",
        tab=tab,
        keys=keys,
        mappings=mappings,
        status_filter=status_filter,
        level_filter=level_filter,
        car2_base_url=current_app.config.get("CAR2_CODES_BASE_URL", ""),
    )


@admin_bp.route("/developer/keys", methods=["POST"])
@login_required
@admin_required
def developer_issue_key():
    name = (request.form.get("name") or "unnamed").strip()
    _row, plain = api_key_service.issue_api_key(name, created_by=current_user.username)
    flash(
        f"API 키가 발급되었습니다. 아래 키는 이번에만 표시됩니다: {plain}",
        "warning",
    )
    return redirect(url_for("admin.developer", tab="keys"))


@admin_bp.route("/developer/keys/<int:key_id>/revoke", methods=["POST"])
@login_required
@admin_required
def developer_revoke_key(key_id):
    if api_key_service.revoke_api_key(key_id):
        flash("API 키를 폐기했습니다.", "success")
    else:
        flash("키를 찾을 수 없거나 이미 폐기되었습니다.", "danger")
    return redirect(url_for("admin.developer", tab="keys"))


@admin_bp.route("/developer/mapping/sync", methods=["POST"])
@login_required
@admin_required
def developer_mapping_sync():
    result = code_mapping_sync.sync_candidates_from_car2()
    if result.get("ok"):
        flash(
            f"동기화 완료: {result['created']}건 생성, {result['skipped']}건 건너뜀",
            "success",
        )
    else:
        flash(f"동기화 실패: {result.get('error')}", "danger")
    return redirect(url_for("admin.developer", tab="mapping"))


@admin_bp.route("/developer/mapping/<int:mapping_id>/status", methods=["POST"])
@login_required
@admin_required
def developer_mapping_status(mapping_id):
    status = request.form.get("status", "")
    if code_mapping_sync.set_mapping_status(mapping_id, status):
        flash(f"상태를 {status}(으)로 변경했습니다.", "success")
    else:
        flash("상태 변경에 실패했습니다.", "danger")
    qs = {"tab": "mapping"}
    if request.form.get("return_status"):
        qs["status"] = request.form.get("return_status")
    if request.form.get("return_level"):
        qs["level"] = request.form.get("return_level")
    return redirect(url_for("admin.developer", **qs))


@admin_bp.route("/developer/mapping/manual", methods=["POST"])
@login_required
@admin_required
def developer_mapping_manual():
    level = (request.form.get("level") or "").strip()
    car2_code = (request.form.get("car2_code") or "").strip()
    car1_code = (request.form.get("car1_code") or "").strip()
    force = request.form.get("force") == "1"
    if not level or not car2_code or not car1_code:
        flash("level, car2_code, car1_code는 필수입니다.", "danger")
        return redirect(url_for("admin.developer", tab="mapping"))

    existing = db.session.execute(
        db.select(VehicleCodeMapping).where(
            VehicleCodeMapping.level == level,
            VehicleCodeMapping.car2_code == car2_code,
        )
    ).scalar_one_or_none()
    car2_name = (request.form.get("car2_name") or "").strip() or None
    car1_name = (request.form.get("car1_name") or "").strip() or None
    if existing and existing.status in ("confirmed", "rejected") and not force:
        flash("confirmed/rejected 매핑은 force=1 없이 덮어쓸 수 없습니다.", "warning")
        return redirect(url_for("admin.developer", tab="mapping"))
    if code_mapping_sync.confirmed_car1_conflict(level, car1_code, exclude_car2=car2_code):
        flash("동일 car1_code에 다른 confirmed 매핑이 이미 있습니다.", "danger")
        return redirect(url_for("admin.developer", tab="mapping"))
    if existing:
        existing.car1_code = car1_code
        existing.car2_name = car2_name
        existing.car1_name = car1_name
        existing.status = "confirmed"
        existing.source = "manual"
    else:
        db.session.add(
            VehicleCodeMapping(
                level=level,
                car2_code=car2_code,
                car1_code=car1_code,
                car2_name=car2_name,
                car1_name=car1_name,
                status="confirmed",
                source="manual",
            )
        )
    db.session.commit()
    flash("매핑을 저장했습니다.", "success")
    return redirect(url_for("admin.developer", tab="mapping"))


@admin_bp.route("/developer/mapping/import", methods=["POST"])
@login_required
@admin_required
def developer_mapping_import():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("CSV 파일을 선택하세요.", "danger")
        return redirect(url_for("admin.developer", tab="mapping"))
    text = file.read().decode("utf-8-sig")
    force = request.form.get("force") == "1"
    result = code_mapping_sync.import_csv(text, force=force)
    if result.get("ok"):
        flash(
            f"CSV 가져오기 완료: {result['created']}건 생성, {result['updated']}건 갱신, "
            f"{result.get('skipped', 0)}건 건너뜀",
            "success",
        )
    else:
        flash(f"CSV 가져오기 실패: {result.get('error')}", "danger")
    return redirect(url_for("admin.developer", tab="mapping"))


@admin_bp.route("/developer/mapping/export")
@login_required
@admin_required
def developer_mapping_export():
    csv_text = code_mapping_sync.export_csv()
    resp = make_response(csv_text)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=vehicle_code_mapping.csv"
    return resp


@admin_bp.route("/analysis-logic")
@login_required
@admin_required
def analysis_logic():
    tab = request.args.get("tab", "docs")
    if tab not in ("docs", "logics"):
        tab = "docs"

    logics = []
    edit_row = None
    if tab == "logics":
        logics = analysis_logic_service.list_logics()
        edit_id = request.args.get("edit", type=int)
        if edit_id:
            edit_row = db.session.get(AnalysisLogic, edit_id)

    return render_template(
        "admin_analysis_logic.html",
        tab=tab,
        logics=logics,
        edit_row=edit_row,
    )


@admin_bp.route("/analysis-logic/toggle/<int:logic_id>", methods=["POST"])
@login_required
@admin_required
def analysis_logic_toggle(logic_id):
    row = db.session.get(AnalysisLogic, logic_id)
    if not row:
        flash("로직을 찾을 수 없습니다.", "danger")
        return redirect(url_for("admin.analysis_logic", tab="logics"))
    analysis_logic_service.set_active(logic_id, not row.is_active)
    state = "활성" if not row.is_active else "비활성"
    flash(f"{row.name}을(를) {state}(으)로 변경했습니다.", "success")
    return redirect(url_for("admin.analysis_logic", tab="logics"))


@admin_bp.route("/analysis-logic/save", methods=["POST"])
@login_required
@admin_required
def analysis_logic_save():
    logic_id = request.form.get("logic_id", type=int)
    code = (request.form.get("code") or "").strip()
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    category = (request.form.get("category") or "custom").strip()
    is_active = request.form.get("is_active") == "on"
    params_raw = (request.form.get("params") or "{}").strip()

    existing = db.session.get(AnalysisLogic, logic_id) if logic_id else None
    if existing:
        code = existing.code
    if not code or not name:
        flash("code와 name은 필수입니다.", "danger")
        return redirect(url_for("admin.analysis_logic", tab="logics", edit=logic_id))

    try:
        params = json.loads(params_raw) if params_raw else {}
    except json.JSONDecodeError:
        flash("params JSON 형식이 올바르지 않습니다.", "danger")
        return redirect(url_for("admin.analysis_logic", tab="logics", edit=logic_id))

    try:
        analysis_logic_service.upsert(
            code=code,
            name=name,
            description=description,
            category=category,
            params=params,
            is_active=is_active,
            is_builtin=existing.is_builtin if existing else False,
            updated_by=current_user.username,
        )
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.analysis_logic", tab="logics", edit=logic_id))

    flash("분석 로직을 저장했습니다.", "success")
    return redirect(url_for("admin.analysis_logic", tab="logics"))


@admin_bp.route("/analysis-logic/delete/<int:logic_id>", methods=["POST"])
@login_required
@admin_required
def analysis_logic_delete(logic_id):
    ok, msg = analysis_logic_service.delete_logic(logic_id)
    if ok:
        flash("로직을 삭제했습니다.", "success")
    elif msg == "built-in logic cannot be deleted":
        flash("내장 로직은 삭제할 수 없습니다.", "warning")
    else:
        flash("로직을 찾을 수 없습니다.", "danger")
    return redirect(url_for("admin.analysis_logic", tab="logics"))


@admin_bp.route("/analysis-logic/seed", methods=["POST"])
@login_required
@admin_required
def analysis_logic_seed():
    created = analysis_logic_service.seed_builtin_logics()
    if created:
        flash(f"내장 로직 {created}건을 추가했습니다.", "success")
    else:
        flash("내장 로직이 이미 최신 상태입니다.", "info")
    return redirect(url_for("admin.analysis_logic", tab="logics"))
