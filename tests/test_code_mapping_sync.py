import csv
import io
from unittest.mock import patch

import pytest


def _mock_response(json_data):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return json_data

    return Resp()


def test_sync_creates_candidate_from_mocked_makers(db, app):
    from app.models import VehicleCodeMapping, VehicleMaker
    from app.services.code_mapping_sync import sync_candidates_from_car2

    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_h", maker_name="현대"))
        db.session.commit()

        def fake_get(url, params=None, timeout=None):
            if url.endswith("/api/codes/makers"):
                return _mock_response(
                    {"ok": True, "items": [{"maker_no": "C2H", "maker_name": "현대"}]}
                )
            return _mock_response([])

        with patch("app.services.code_mapping_sync.requests.get", side_effect=fake_get):
            result = sync_candidates_from_car2(base_url="http://car2.test")

        assert result["ok"] is True
        assert result["created"] == 1
        assert result["error"] is None

        row = db.session.execute(
            db.select(VehicleCodeMapping).where(
                VehicleCodeMapping.level == "maker",
                VehicleCodeMapping.car2_code == "C2H",
            )
        ).scalar_one()
        assert row.car1_code == "mk_h"
        assert row.status == "candidate"
        assert row.source == "sync"


def test_sync_skips_confirmed_mapping(db, app):
    from app.models import VehicleCodeMapping, VehicleMaker
    from app.services.code_mapping_sync import sync_candidates_from_car2

    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_h", maker_name="현대"))
        db.session.add(
            VehicleCodeMapping(
                level="maker",
                car2_code="C2H",
                car1_code="mk_h",
                car2_name="현대",
                car1_name="현대",
                status="confirmed",
                source="manual",
            )
        )
        db.session.commit()

        def fake_get(url, params=None, timeout=None):
            if url.endswith("/api/codes/makers"):
                return _mock_response(
                    [{"maker_no": "C2H", "maker_name": "현대"}]
                )
            return _mock_response([])

        with patch("app.services.code_mapping_sync.requests.get", side_effect=fake_get):
            result = sync_candidates_from_car2(base_url="http://car2.test")

        assert result["ok"] is True
        assert result["created"] == 0
        assert result["skipped"] >= 1


def test_import_csv_skips_protected_without_force(db, app):
    from app.models import VehicleCodeMapping
    from app.services.code_mapping_sync import import_csv

    with app.app_context():
        db.session.add(
            VehicleCodeMapping(
                level="maker",
                car2_code="C2H",
                car1_code="mk_h",
                car2_name="현대",
                car1_name="현대",
                status="confirmed",
                source="manual",
            )
        )
        db.session.commit()

        text = (
            "level,car2_code,car1_code,car2_name,car1_name\n"
            "maker,C2H,mk_other,현대,다른현대\n"
        )
        result = import_csv(text)
        assert result["ok"] is True
        assert result["updated"] == 0
        assert result["skipped"] == 1

        row = db.session.execute(
            db.select(VehicleCodeMapping).where(
                VehicleCodeMapping.car2_code == "C2H"
            )
        ).scalar_one()
        assert row.car1_code == "mk_h"


def test_import_csv_force_overwrites_protected(db, app):
    from app.models import VehicleCodeMapping
    from app.services.code_mapping_sync import import_csv

    with app.app_context():
        db.session.add(
            VehicleCodeMapping(
                level="maker",
                car2_code="C2H",
                car1_code="mk_h",
                car2_name="현대",
                car1_name="현대",
                status="confirmed",
                source="manual",
            )
        )
        db.session.commit()

        text = (
            "level,car2_code,car1_code,car2_name,car1_name\n"
            "maker,C2H,mk_other,현대,다른현대\n"
        )
        result = import_csv(text, force=True)
        assert result["ok"] is True
        assert result["updated"] == 1
        assert result["skipped"] == 0

        row = db.session.execute(
            db.select(VehicleCodeMapping).where(
                VehicleCodeMapping.car2_code == "C2H"
            )
        ).scalar_one()
        assert row.car1_code == "mk_other"


def test_set_mapping_status_rejects_confirmed_car1_conflict(db, app):
    from app.models import VehicleCodeMapping
    from app.services.code_mapping_sync import set_mapping_status

    with app.app_context():
        db.session.add(
            VehicleCodeMapping(
                level="maker",
                car2_code="C2A",
                car1_code="mk_h",
                status="confirmed",
                source="manual",
            )
        )
        candidate = VehicleCodeMapping(
            level="maker",
            car2_code="C2B",
            car1_code="mk_h",
            status="candidate",
            source="sync",
        )
        db.session.add(candidate)
        db.session.commit()

        assert set_mapping_status(candidate.id, "confirmed") is False
        assert db.session.get(VehicleCodeMapping, candidate.id).status == "candidate"


def test_import_csv_upserts_confirmed(db, app):
    from app.models import VehicleCodeMapping
    from app.services.code_mapping_sync import import_csv

    text = (
        "level,car2_code,car1_code,car2_name,car1_name\n"
        "maker,C2K,mk_kia,기아,기아\n"
    )

    with app.app_context():
        result = import_csv(text)
        assert result["ok"] is True
        assert result["created"] == 1

        row = db.session.execute(
            db.select(VehicleCodeMapping).where(
                VehicleCodeMapping.car2_code == "C2K"
            )
        ).scalar_one()
        assert row.status == "confirmed"
        assert row.source == "csv"


def test_export_csv(db, app):
    from app.models import VehicleCodeMapping
    from app.services.code_mapping_sync import export_csv

    with app.app_context():
        db.session.add(
            VehicleCodeMapping(
                level="maker",
                car2_code="C2H",
                car1_code="mk_h",
                car2_name="현대",
                car1_name="현대",
                status="confirmed",
                source="csv",
            )
        )
        db.session.commit()

        text = export_csv()
        rows = list(csv.DictReader(io.StringIO(text)))
        assert rows[0]["car2_code"] == "C2H"
        assert rows[0]["level"] == "maker"


def test_set_mapping_status(db, app):
    from app.models import VehicleCodeMapping
    from app.services.code_mapping_sync import set_mapping_status

    with app.app_context():
        m = VehicleCodeMapping(
            level="maker",
            car2_code="C2X",
            car1_code="mk_x",
            status="candidate",
            source="sync",
        )
        db.session.add(m)
        db.session.commit()

        assert set_mapping_status(m.id, "confirmed") is True
        assert db.session.get(VehicleCodeMapping, m.id).status == "confirmed"
        assert set_mapping_status(99999, "confirmed") is False
