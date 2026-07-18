from functools import wraps

from flask import abort, jsonify, request
from flask_login import current_user


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.path.startswith("/api") or request.is_json:
                return jsonify({"error": "인증이 필요합니다."}), 401
            abort(401)
        if not getattr(current_user, "is_admin", False):
            if request.path.startswith("/api") or request.is_json:
                return jsonify({"error": "관리자 권한이 필요합니다."}), 403
            abort(403)
        return fn(*args, **kwargs)

    return wrapper
