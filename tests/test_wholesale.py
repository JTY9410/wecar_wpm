def test_wholesale_prices_resolves_mapped_maker(client, db, app):
    from app.models import MarketSummary, VehicleMaker, VehicleCodeMapping

    app.config["EXTERNAL_API_KEY"] = "k"
    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_h", maker_name="현대"))
        db.session.add(
            VehicleCodeMapping(
                level="maker",
                car2_code="C2H",
                car1_code="mk_h",
                status="confirmed",
                source="manual",
            )
        )
        db.session.add(
            MarketSummary(
                car_code="x",
                maker="현대",
                model_name="쏘나타",
                mdetail_name="DN8",
                grade_name="프리미엄",
                gdetail_name="-",
                car_year=2020,
                fuel="가솔린",
                awd="2WD",
                imported="국산",
                is_accident_free=True,
                km_bin="0-1.5만",
                hammer_avg=1500,
                sample_count=3,
            )
        )
        db.session.commit()
    r = client.get("/api/v1/wholesale/prices?maker_no=C2H", headers={"X-API-Key": "k"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] >= 1
    assert data["resolved"]["maker_no"] == "mk_h"
    assert data["resolved"]["car2"]["maker_no"] == "C2H"


def test_codes_grades_endpoint(client, app):
    app.config["EXTERNAL_API_KEY"] = "k"
    r = client.get("/api/v1/wholesale/codes/grades", headers={"X-API-Key": "k"})
    assert r.status_code == 200
    assert "items" in r.get_json()


def test_codes_modeldetails_endpoint(client, db, app):
    from app.models import VehicleMaker, VehicleModel, VehicleModelDetail

    app.config["EXTERNAL_API_KEY"] = "k"
    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_h", maker_name="현대"))
        db.session.add(VehicleModel(model_no="md_s", maker_no="mk_h", model_name="쏘나타"))
        db.session.add(
            VehicleModelDetail(mdetail_no="mdt_dn8", model_no="md_s", mdetail_name="DN8")
        )
        db.session.commit()
    r = client.get(
        "/api/v1/wholesale/codes/modeldetails?model_no=md_s",
        headers={"X-API-Key": "k"},
    )
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert len(items) == 1
    assert items[0]["mdetail_name"] == "DN8"


def test_lookup_includes_resolved(client, db, app):
    from app.models import MarketSummary, VehicleMaker, VehicleCodeMapping

    app.config["EXTERNAL_API_KEY"] = "k"
    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_h", maker_name="현대"))
        db.session.add(
            VehicleCodeMapping(
                level="maker",
                car2_code="C2H",
                car1_code="mk_h",
                status="confirmed",
                source="manual",
            )
        )
        db.session.add(
            MarketSummary(
                car_code="x",
                maker="현대",
                model_name="쏘나타",
                mdetail_name="DN8",
                grade_name="프리미엄",
                gdetail_name="-",
                car_year=2020,
                fuel="가솔린",
                awd="2WD",
                imported="국산",
                is_accident_free=True,
                km_bin="0-1.5만",
                hammer_avg=1500,
                sample_count=3,
            )
        )
        db.session.commit()
    r = client.get(
        "/api/v1/wholesale/lookup?maker_no=C2H&model=쏘나타",
        headers={"X-API-Key": "k"},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] >= 1
    assert data["resolved"]["maker_no"] == "mk_h"
