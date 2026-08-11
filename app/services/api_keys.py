from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timezone

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import ApiKey


def _utcnow():
    return datetime.now(timezone.utc)


def issue_api_key(name: str, created_by: str | None = None) -> tuple[ApiKey, str]:
    plain = "wpm_" + secrets.token_hex(24)
    row = ApiKey(
        name=(name or "unnamed").strip()[:120],
        key_prefix=plain[:12],
        key_hash=generate_password_hash(plain, method="scrypt"),
        is_active=True,
        created_by=(created_by or "")[:80] or None,
    )
    db.session.add(row)
    db.session.commit()
    return row, plain


def has_any_auth_configured() -> bool:
    env = (current_app.config.get("EXTERNAL_API_KEY") or "").strip()
    if env:
        return True
    n = db.session.scalar(
        db.select(db.func.count()).select_from(ApiKey).where(ApiKey.is_active.is_(True))
    )
    return bool(n)


def verify_api_key(provided: str) -> ApiKey | str | None:
    provided = (provided or "").strip()
    if not provided:
        return None
    rows = db.session.execute(
        db.select(ApiKey).where(ApiKey.is_active.is_(True))
    ).scalars().all()
    for row in rows:
        if check_password_hash(row.key_hash, provided):
            row.last_used_at = _utcnow()
            db.session.commit()
            return row
    expected = (current_app.config.get("EXTERNAL_API_KEY") or "").strip()
    if expected and hmac.compare_digest(provided, expected):
        return "env"
    return None


def revoke_api_key(key_id: int) -> bool:
    row = db.session.get(ApiKey, key_id)
    if not row or not row.is_active:
        return False
    row.is_active = False
    row.revoked_at = _utcnow()
    db.session.commit()
    return True
