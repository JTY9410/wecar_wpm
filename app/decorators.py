from functools import wraps

from flask import abort, jsonify, request
from flask_login import current_user


def _wants_json():
    if request.path.startswith("/api") or request.is_json:
        return True
    # admin POST endpoints are consumed by fetch() and expect JSON
    if request.path.startswith("/admin") and request.method != "GET":
        return True
    best = request.accept_mimetypes.best
    return best == "application/json"


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            if _wants_json():
                return jsonify({"error": "인증이 필요합니다."}), 401
            abort(401)
        if not getattr(current_user, "is_admin", False):
            if _wants_json():
                return jsonify({"error": "관리자 권한이 필요합니다."}), 403
            abort(403)
        return fn(*args, **kwargs)

    return wrapper
