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


def test_api_key_and_mapping_tables(db):
    from app.models import ApiKey, VehicleCodeMapping
    from werkzeug.security import generate_password_hash

    k = ApiKey(
        name="test",
        key_prefix="wpm_test",
        key_hash=generate_password_hash("wpm_secret", method="scrypt"),
        is_active=True,
    )
    m = VehicleCodeMapping(
        level="maker",
        car2_code="c2_mk_1",
        car1_code="mk_hyundai",
        car2_name="현대",
        car1_name="현대",
        status="confirmed",
        source="manual",
        match_score=1.0,
    )
    db.session.add_all([k, m])
    db.session.commit()
    assert db.session.get(ApiKey, k.id).key_prefix == "wpm_test"
    assert db.session.get(VehicleCodeMapping, m.id).level == "maker"
