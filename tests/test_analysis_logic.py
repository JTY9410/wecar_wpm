def test_analysis_logic_persist(db, app):
    from app.models import AnalysisLogic
    with app.app_context():
        row = AnalysisLogic(
            code="mileage.km_bin",
            name="KM구간",
            category="ingest",
            is_builtin=True,
            is_active=True,
            params={"step": 15000, "max": 200000},
            sort_order=10,
        )
        db.session.add(row)
        db.session.commit()
        assert db.session.get(AnalysisLogic, row.id).code == "mileage.km_bin"
