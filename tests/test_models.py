from app.extensions import db
from app.models import User
from app.services.seed import seed_admin


def test_admin_seed_idempotent(app, db):
    seed_admin(app)
    seed_admin(app)
    admins = db.session.execute(db.select(User).where(User.username == "wecar")).scalars().all()
    assert len(admins) == 1
    assert admins[0].role == "ADMIN"
    assert admins[0].check_password("1004wecar")
    assert not admins[0].check_password("wrong")
