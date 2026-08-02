from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for

from config import Config
from app.extensions import db, login_manager, migrate


def _safe_local_redirect(target: str, fallback: str) -> str:
    """Only allow same-site relative redirects; reject absolute/protocol-relative URLs."""
    if not target:
        return fallback
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return fallback
    return target


def create_app(config_class=Config):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)
    config_class.ensure_dirs()
    app.url_map.strict_slashes = False

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app import models  # noqa: F401  (register models)
    from app.services.i18n_translate import load_pack

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    @app.before_request
    def _capture_lang():
        lang = request.args.get("lang")
        if lang in app.config.get("SUPPORTED_LANGS", ["ko", "en", "ja"]):
            session["lang"] = lang

    @app.context_processor
    def inject_i18n():
        lang = session.get("lang", "ko")
        if lang not in app.config.get("SUPPORTED_LANGS", ["ko", "en", "ja"]):
            lang = "ko"
        pack = load_pack(lang)

        def t(key, default=None):
            return pack.get(key, default if default is not None else key)

        return {"i18n": pack, "lang": lang, "t": t, "supported_langs": app.config.get("SUPPORTED_LANGS")}

    from app.services.i18n_translate import translate as _translate_text

    @app.template_filter("tr")
    def translate_filter(text):
        """차명·지역·색상 등 자유 텍스트를 현재 언어로 번역(정적 사전 우선, 없으면 Google/Gemini)."""
        lang = session.get("lang", "ko")
        if lang not in app.config.get("SUPPORTED_LANGS", ["ko", "en", "ja"]):
            lang = "ko"
        return _translate_text(text, lang)

    from app.routes.auth import auth_bp
    from app.routes.market import market_bp
    from app.routes.listings import listings_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.codes import codes_bp
    from app.routes.wholesale import wholesale_bp
    from app.routes.briefing import briefing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(listings_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(codes_bp)
    app.register_blueprint(wholesale_bp)
    app.register_blueprint(briefing_bp)

    @app.route("/set-lang/<lang>")
    def set_lang(lang):
        if lang in app.config.get("SUPPORTED_LANGS", ["ko", "en", "ja"]):
            session["lang"] = lang
        nxt = request.args.get("next") or request.referrer or url_for("market.index")
        return redirect(_safe_local_redirect(nxt, url_for("market.index")))

    @app.route("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": app.config.get("SERVICE_ID", "wecarcar1"),
                "app": app.config["APP_NAME"],
                "integration_mode": app.config.get("INTEGRATION_MODE", "standalone"),
            }
        )

    @app.route("/service-worker.js")
    def service_worker():
        response = send_from_directory(Path(app.root_path) / "static", "service-worker.js")
        response.headers["Content-Type"] = "application/javascript; charset=utf-8"
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.route("/manifest.json")
    def web_manifest():
        return send_from_directory(Path(app.root_path) / "static", "manifest.json")

    @app.route("/static/storage/car_images/<path:filename>")
    def car_image(filename):
        return send_from_directory(app.config["IMAGE_STORAGE_PATH"], filename)

    @app.errorhandler(401)
    def unauthorized(_e):
        if request.path.startswith("/api") or (
            request.path.startswith("/admin/") and request.method != "GET"
        ):
            return jsonify({"error": "인증이 필요합니다."}), 401
        return redirect(url_for("auth.login"))

    @app.errorhandler(403)
    def forbidden(_e):
        if request.path.startswith("/api") or request.accept_mimetypes.best == "application/json":
            return jsonify({"error": "관리자 권한이 필요합니다.", "toast": "접근 권한이 없습니다."}), 403
        return render_template(
            "error.html",
            code=403,
            message="접근 권한이 없습니다.",
            show_toast=True,
        ), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404,
                               message="페이지를 찾을 수 없습니다."), 404

    @app.cli.command("seed-admin")
    def seed_admin_cmd():
        """Seed the initial ADMIN account from .env (SSOT)."""
        from app.services.seed import seed_admin
        user = seed_admin(app)
        print(f"seeded admin: {user.username} ({user.role})")

    from app.cli import sync_listings_cmd
    app.cli.add_command(sync_listings_cmd)

    # Prefer a dedicated scheduler process/container (ENABLE_SCHEDULER=0 on web).
    if app.config.get("ENABLE_SCHEDULER"):
        from app.services.scheduler import start_scheduler
        start_scheduler(app)

    return app
