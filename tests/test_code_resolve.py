def test_resolve_car1_passthrough(db, app):
    from app.models import VehicleMaker
    from app.services.code_resolve import resolve_vehicle_codes

    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_h", maker_name="현대"))
        db.session.commit()
        out = resolve_vehicle_codes(maker_no="mk_h")
        assert out["maker_no"] == "mk_h"
        assert out["match_level"] == "maker"


def test_resolve_car2_via_mapping(db, app):
    from app.models import VehicleCodeMapping, VehicleMaker
    from app.services.code_resolve import resolve_vehicle_codes

    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_h", maker_name="현대"))
        db.session.add(
            VehicleCodeMapping(
                level="maker",
                car2_code="C2MAKER",
                car1_code="mk_h",
                status="confirmed",
                source="manual",
                car2_name="현대",
                car1_name="현대",
            )
        )
        db.session.commit()
        out = resolve_vehicle_codes(maker_no="C2MAKER")
        assert out["maker_no"] == "mk_h"
        assert out["car2"]["maker_no"] == "C2MAKER"


def test_resolve_by_name_alias(db, app):
    from app.models import VehicleMaker
    from app.services.code_resolve import resolve_vehicle_codes

    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_kia", maker_name="기아"))
        db.session.commit()
        out = resolve_vehicle_codes(maker="기아자동차")
        assert out["maker_no"] == "mk_kia"
