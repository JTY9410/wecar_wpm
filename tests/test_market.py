from app.services.excel_pipeline import process_weekly_upload
from app.services import market_query
from tests.conftest import login
from tests.fixtures.make_fixture import build


def _load(app, tmp_path):
    with app.app_context():
        process_weekly_upload(build(str(tmp_path / "m.xlsx")),
                              week_no="2026-W29", mode="reset")


def test_cascade_and_grid(app, db, tmp_path):
    _load(app, tmp_path)
    makers = market_query.makers()
    assert any(m["value"] == "현대" for m in makers)
    models = market_query.models("현대")
    assert models and all("value" in m and "label" in m for m in models)
    rows = market_query.grid(maker="현대")
    assert rows
    assert "km_bin" in rows[0] and "mom_pct" in rows[0]
    assert rows[0]["maker"] == "현대"


def test_cascade_and_grid_translated_labels(app, db, tmp_path):
    _load(app, tmp_path)
    makers = market_query.makers(lang="en")
    hyundai = next(m for m in makers if m["value"] == "현대")
    assert hyundai["label"] == "Hyundai"
    rows = market_query.grid(maker="현대", lang="en")
    assert rows[0]["maker"] == "현대"
    assert rows[0]["maker_label"] == "Hyundai"
    assert rows[0]["model_name_label"]  # translated display


def test_grid_api_requires_login(client):
    resp = client.get("/api/grid")
    assert resp.status_code in (302, 401)


def test_grid_api_ok(app, client, tmp_path):
    _load(app, tmp_path)
    login(client)
    resp = client.get("/api/grid?maker=현대")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_price_trend_and_forecast_calc(app, tmp_path):
    with app.app_context():
        process_weekly_upload(build(str(tmp_path / "w28.xlsx")), week_no="2026-W28", mode="reset")
        process_weekly_upload(build(str(tmp_path / "w29.xlsx")), week_no="2026-W29", mode="append")

        trend = market_query.price_trend(maker="현대")
        weeks = {w["week_no"] for w in trend}
        assert weeks == {"2026-W28", "2026-W29"}
        for w in trend:
            assert w["sample_count"] > 0

        calc = market_query.forecast_from_trend(trend)
        assert calc["ok"] is True
        assert calc["current_avg"] == trend[-1]["avg_price"]
        assert calc["expected_price"] is not None


def test_forecast_from_trend_empty():
    assert market_query.forecast_from_trend([]) == {"ok": False}


def test_forecast_from_trend_single_week():
    calc = market_query.forecast_from_trend([{"week_no": "2026-W29", "avg_price": 300, "sample_count": 3}])
    assert calc == {"ok": True, "current_avg": 300, "expected_price": 300, "expected_pct": 0.0, "basis": "single_week"}


def test_price_forecast_api_requires_login(client):
    resp = client.get("/api/price-forecast?maker=현대")
    assert resp.status_code in (302, 401)


def test_price_forecast_api_ok(app, client, tmp_path):
    _load(app, tmp_path)
    login(client)
    resp = client.get("/api/price-forecast?maker=현대")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "expected_price" in data
    assert "report" in data


def test_price_forecast_api_no_data(app, client):
    login(client)
    resp = client.get("/api/price-forecast?maker=존재하지않음")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is False
