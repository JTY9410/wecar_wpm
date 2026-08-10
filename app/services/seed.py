from sqlalchemy import func

from app.extensions import db
from app.models import LLMConfig, User


def seed_admin(app):
    """Idempotently seed the initial ADMIN account from config (SSOT)."""
    username = app.config["INIT_ADMIN_USERNAME"]
    password = app.config["INIT_ADMIN_PASSWORD"]
    user = db.session.execute(
        db.select(User).where(User.username == username)
    ).scalar_one_or_none()
    if user is None:
        user = User(username=username, role="ADMIN", is_approved=True, name="관리자")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    else:
        if not user.is_approved:
            user.is_approved = True
            db.session.commit()
    # Default LLM providers row (gemini active).
    llm_count = db.session.scalar(db.select(func.count()).select_from(LLMConfig)) or 0
    if llm_count == 0:
        db.session.add_all([
            LLMConfig(provider="gemini", is_active=True, model_name=app.config["GEMINI_MODEL"]),
            LLMConfig(provider="openai", is_active=False, model_name="gpt-4o-mini"),
            LLMConfig(provider="claude", is_active=False, model_name="claude-3-5-sonnet-20241022"),
        ])
        db.session.commit()
    return user
