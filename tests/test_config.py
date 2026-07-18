from config import Config


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_business_constants():
    assert Config.SYNC_HOURS == [9, 13, 18]
    assert Config.RATE_LIMIT_DAILY == 20
    assert Config.API_TIMEOUT == 120
    assert Config.KM_BUCKET_STEP == 15000
