from app.models import User
from app.services.seed import seed_admin


def test_admin_seed_idempotent(app, db):
    seed_admin(app)
    seed_admin(app)
    admins = User.query.filter_by(username="wecar").all()
    assert len(admins) == 1
    assert admins[0].role == "ADMIN"
    assert admins[0].check_password("1004wecar")
    assert not admins[0].check_password("wrong")
