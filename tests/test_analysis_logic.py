def test_analysis_logic_persist(db, app):
    from app.models import AnalysisLogic
    with app.app_context():
        row = AnalysisLogic(
            code="test.persist",
            name="테스트",
            category="custom",
            is_builtin=False,
            is_active=True,
            params={},
            sort_order=99,
        )
        db.session.add(row)
        db.session.commit()
        assert db.session.get(AnalysisLogic, row.id).code == "test.persist"


def test_seed_builtin_logics_creates_seven(db, app):
    from app.models import AnalysisLogic
    from app.services.analysis_logic import BUILTIN_SPECS, seed_builtin_logics

    with app.app_context():
        db.session.execute(db.delete(AnalysisLogic))
        db.session.commit()
        created = seed_builtin_logics()
        assert created == 7
        assert db.session.scalar(
            db.select(db.func.count()).select_from(AnalysisLogic)
        ) == 7
        codes = {s["code"] for s in BUILTIN_SPECS}
        rows = db.session.execute(db.select(AnalysisLogic)).scalars().all()
        assert {r.code for r in rows} == codes


def test_seed_builtin_logics_idempotent_preserves_params(db, app):
    from app.models import AnalysisLogic
    from app.services.analysis_logic import seed_builtin_logics

    with app.app_context():
        seed_builtin_logics()
        row = db.session.execute(
            db.select(AnalysisLogic).where(AnalysisLogic.code == "mileage.km_bin")
        ).scalar_one()
        row.params = {"step": 99999, "max": 88888}
        row.is_active = False
        db.session.commit()

        created = seed_builtin_logics()
        assert created == 0
        db.session.refresh(row)
        assert row.params == {"step": 99999, "max": 88888}
        assert row.is_active is False


def test_delete_logic_builtin_fails(db, app):
    from app.models import AnalysisLogic
    from app.services.analysis_logic import delete_logic, seed_builtin_logics

    with app.app_context():
        seed_builtin_logics()
        row = db.session.execute(
            db.select(AnalysisLogic).where(AnalysisLogic.code == "mileage.km_bin")
        ).scalar_one()
        ok, msg = delete_logic(row.id)
        assert ok is False
        assert msg
        assert db.session.get(AnalysisLogic, row.id) is not None


def test_upsert_custom_and_delete_ok(db, app):
    from app.models import AnalysisLogic
    from app.services.analysis_logic import delete_logic, upsert

    with app.app_context():
        row = upsert(
            code="custom.demo",
            name="데모",
            description="테스트",
            category="custom",
            params={},
            is_active=True,
            is_builtin=False,
        )
        assert row.id is not None
        assert row.is_builtin is False

        ok, msg = delete_logic(row.id)
        assert ok is True
        assert msg == ""
        assert db.session.get(AnalysisLogic, row.id) is None


def test_validate_params_rejects_threshold_200(db, app):
    import pytest

    from app.services.analysis_logic import validate_params

    with app.app_context():
        with pytest.raises(ValueError):
            validate_params(
                "briefing.price_alert",
                {"threshold_pct": 200, "min_samples": 2},
            )


def test_is_active_missing_row_defaults_true(db, app):
    from app.services.analysis_logic import is_active

    with app.app_context():
        assert is_active("aggregate.market_summary") is True


def test_get_params_merges_db_over_defaults(db, app):
    from app.models import AnalysisLogic
    from app.services.analysis_logic import get_params, seed_builtin_logics

    with app.app_context():
        seed_builtin_logics()
        row = db.session.execute(
            db.select(AnalysisLogic).where(AnalysisLogic.code == "briefing.price_alert")
        ).scalar_one()
        row.params = {"threshold_pct": 10.0}
        db.session.commit()

        params = get_params("briefing.price_alert")
        assert params["threshold_pct"] == 10.0
        assert params["min_samples"] == 2
