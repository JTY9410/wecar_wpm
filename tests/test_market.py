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
    assert "현대" in makers
    models = market_query.models("현대")
    assert models
    rows = market_query.grid(maker="현대")
    assert rows
    assert "km_bin" in rows[0] and "mom_pct" in rows[0]


def test_grid_api_requires_login(client):
    resp = client.get("/api/grid")
    assert resp.status_code in (302, 401)


def test_grid_api_ok(app, client, tmp_path):
    _load(app, tmp_path)
    login(client)
    resp = client.get("/api/grid?maker=현대")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)
