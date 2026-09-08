import os
import tempfile

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///instance/test.db")

from app import create_app
from app.extensions import db as _db
from app.services.seed import seed_admin
from config import Config


@pytest.fixture()
def app():
    tmp = tempfile.mkdtemp()

    class TestConfig(Config):
        # Flask-SQLAlchemy binds its engine at db.init_app() time, so the test
        # DB URI must be set on the config CLASS passed into create_app() —
        # updating app.config afterwards has no effect on the already-bound engine.
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(tmp, 'test.db')}"
        TESTING = True
        UPLOAD_SYNC = True
        WTF_CSRF_ENABLED = False
        LOGIN_DISABLED = False

    app = create_app(config_class=TestConfig)
    with app.app_context():
        _db.create_all()
        seed_admin(app)
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return _db


def login(client, username="wecar", password="1004wecar"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=True)
