from app.services import market_query
from app.services.excel_pipeline import process_weekly_upload
from app.services.i18n_translate import load_pack
from tests.fixtures.make_fixture import build


def test_matrix_and_samples(app, db, tmp_path):
    mini = build(str(tmp_path / "mini.xlsx"))
    process_weekly_upload(mini, week_no="2026-W29", mode="append")
    mat = market_query.matrix(maker="현대", model_name="그랜저")
    assert mat["years"]
    assert mat["buckets"]
    assert mat["total_samples"] >= 1

    samp = market_query.samples(maker="현대", model_name="그랜저", lang="en")
    assert samp["ok"] is True
    assert samp["count"] >= 1
    assert "car_name" in samp["items"][0]


def test_i18n_packs():
    ko = load_pack("ko")
    en = load_pack("en")
    ja = load_pack("ja")
    assert ko["matrix"] == "매트릭스"
    assert en["samples"] == "Details"
    assert ja["matrix"] == "マトリックス"


def test_set_lang_and_matrix_api(client, app, db, tmp_path):
    from tests.conftest import login

    mini = build(str(tmp_path / "mini.xlsx"))
    with app.app_context():
        process_weekly_upload(mini, week_no="2026-W29", mode="append")
    login(client)
    r = client.get("/set-lang/en", follow_redirects=False)
    assert r.status_code in (302, 301)
    r = client.get("/api/matrix?maker=%ED%98%84%EB%8C%80")
    assert r.status_code == 200
    data = r.get_json()
    assert "years" in data
    r = client.get("/api/samples?maker=%ED%98%84%EB%8C%80&model_name=%EA%B7%B8%EB%9E%9C%EC%A0%80")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
