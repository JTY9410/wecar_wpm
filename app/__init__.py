import os

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, url_for

from config import Config
from app.extensions import db, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)
    config_class.ensure_dirs()

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app import models  # noqa: F401  (register models)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.market import market_bp
    from app.routes.listings import listings_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.codes import codes_bp
    from app.routes.wholesale import wholesale_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(listings_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(codes_bp)
    app.register_blueprint(wholesale_bp)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "app": app.config["APP_NAME"]})

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

    if app.config.get("ENABLE_SCHEDULER"):
        from app.services.scheduler import start_scheduler
        start_scheduler(app)

    return app
