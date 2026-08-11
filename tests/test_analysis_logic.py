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


def _seed_briefing_weeks(db):
    from app.models import AuctionRecord

    db.session.add_all([
        AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="쏘나타",
            mdetail_name="쏘나타 DN8", grade_name="가솔린 2.0", gdetail_name="스마트",
            hammer_price=1100, car_year=2021, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="쏘나타",
            mdetail_name="쏘나타 DN8", grade_name="가솔린 2.0", gdetail_name="스마트",
            hammer_price=1100, car_year=2021, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W29", maker="현대", model_name="쏘나타",
            mdetail_name="쏘나타 DN8", grade_name="가솔린 2.0", gdetail_name="스마트",
            hammer_price=1000, car_year=2021, km_bin="3~4.5만", fuel="가솔린",
        ),
        AuctionRecord(
            week_no="2026-W29", maker="현대", model_name="쏘나타",
            mdetail_name="쏘나타 DN8", grade_name="가솔린 2.0", gdetail_name="스마트",
            hammer_price=1000, car_year=2021, km_bin="3~4.5만", fuel="가솔린",
        ),
    ])
    db.session.commit()


def test_price_alert_threshold_from_db(db, app):
    from app.models import AnalysisLogic
    from app.services.analysis_logic import seed_builtin_logics
    from app.services.weekly_briefing import build_briefing

    with app.app_context():
        seed_builtin_logics()
        row = db.session.execute(
            db.select(AnalysisLogic).where(AnalysisLogic.code == "briefing.price_alert")
        ).scalar_one()
        row.params = {"threshold_pct": 99.0, "min_samples": 2}
        db.session.commit()
        _seed_briefing_weeks(db)

        data = build_briefing()
        smart = next(r for r in data["rows"] if r["gdetail_name"] == "스마트")
        assert smart["price_pct"] == 10.0
        assert smart["price_flag"] is False
        assert data["price_alerts"] == []


def test_aggregate_off_skips_rebuild(db, app):
    from app.models import AnalysisLogic, AuctionRecord, MarketSummary
    from app.services.analysis_logic import seed_builtin_logics
    from app.services.excel_pipeline import rebuild_market_summary

    with app.app_context():
        seed_builtin_logics()
        db.session.add(AuctionRecord(
            week_no="2026-W30", maker="현대", model_name="아반떼",
            hammer_price=1500, car_year=2020, km_bin="0만~1.5만km",
        ))
        db.session.add(MarketSummary(
            maker="현대", model_name="아반떼", car_year=2020,
            km_bin="0만~1.5만km", hammer_avg=1500, sample_count=1,
            week_no="2026-W30",
        ))
        db.session.commit()
        before = db.session.scalar(
            db.select(db.func.count()).select_from(MarketSummary)
        )

        row = db.session.execute(
            db.select(AnalysisLogic).where(AnalysisLogic.code == "aggregate.market_summary")
        ).scalar_one()
        row.is_active = False
        db.session.commit()

        result = rebuild_market_summary("2026-W30")
        after = db.session.scalar(
            db.select(db.func.count()).select_from(MarketSummary)
        )
        assert result == 0
        assert after == before == 1


def test_mileage_bin_params_from_db(db, app):
    from app.models import AnalysisLogic
    from app.services.analysis_logic import seed_builtin_logics
    from app.services.mileage import calculate_mileage_bin

    with app.app_context():
        seed_builtin_logics()
        row = db.session.execute(
            db.select(AnalysisLogic).where(AnalysisLogic.code == "mileage.km_bin")
        ).scalar_one()
        row.params = {"step": 10000, "max": 100000}
        db.session.commit()

        assert calculate_mileage_bin(5000) == "0만~1만km"
        assert calculate_mileage_bin(15000) == "1만~2만km"
        assert calculate_mileage_bin(100000) == "10만km 이상"
        assert calculate_mileage_bin(5000, step=15000) == "0만~1.5만km"


def test_price_model_inactive_skips_train(db, app, tmp_path):
    from app.models import AnalysisLogic, AuctionRecord
    from app.services.analysis_logic import seed_builtin_logics
    from app.services.price_model import PriceModel

    with app.app_context():
        seed_builtin_logics()
        for i in range(10):
            db.session.add(AuctionRecord(
                week_no="2026-W29", maker="현대", car_year=2018,
                car_km=50000, imported="수출", hammer_price=300 + i * 10,
            ))
        db.session.commit()
        row = db.session.execute(
            db.select(AnalysisLogic).where(AnalysisLogic.code == "predict.random_forest")
        ).scalar_one()
        row.is_active = False
        db.session.commit()

        model = PriceModel(path=str(tmp_path / "m.pkl"))
        res = model.train()
        assert res["trained"] is False
        assert res["reason"] == "inactive"
        assert model.predict("현대", 2018, 50000, "수출") is None


def test_hedonic_inactive_skips_predict(db, app, tmp_path):
    from app.models import AnalysisLogic
    from app.services.analysis_logic import seed_builtin_logics
    from app.services.hedonic_model import HedonicModel

    with app.app_context():
        seed_builtin_logics()
        row = db.session.execute(
            db.select(AnalysisLogic).where(AnalysisLogic.code == "predict.hedonic")
        ).scalar_one()
        row.is_active = False
        db.session.commit()

        model = HedonicModel(path=str(tmp_path / "h.pkl"))
        assert model.predict_detail(maker="현대", car_year=2020, car_km=30000) is None
