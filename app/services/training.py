"""Train vs serve gate. Web deploy serves pickled models; local may retrain."""
from flask import current_app, has_app_context

from config import Config


def training_allowed() -> bool:
    if has_app_context():
        return bool(current_app.config.get("ENABLE_TRAINING", True))
    return bool(getattr(Config, "ENABLE_TRAINING", True))
