from app.models import Listing, SyncLog
from app.services import sync_engine
from app.services.api_client import ApiUnavailable, fetch_listings


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    """Primary always fails; fallback returns data."""
    def __init__(self, primary_ok=False):
        self.primary_ok = primary_ok
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        if "carmanager" in url:  # fallback host
            return FakeResp({"data": [{"CarNo": "F1", "CarName": "폴백차"}]})
        if self.primary_ok:
            return FakeResp({"data": [{"CarNo": "P1", "CarName": "정상차"}]})
        return FakeResp({}, status=500)


def test_fallback_triggered(app, db, monkeypatch):
    session = FakeSession(primary_ok=False)
    data, source = fetch_listings(session=session)
    assert source == "fallback"
    assert data["data"][0]["CarNo"] == "F1"


def test_all_fail_raises():
    class Dead:
        def get(self, url, timeout=None):
            raise RuntimeError("network down")
    try:
        fetch_listings(session=Dead())
        assert False, "should raise"
    except ApiUnavailable:
        pass


def test_sync_marks_missing_as_sold(app, db):
    db.session.add(Listing(car_no="OLD1", car_name="이전매물", is_sold=False))
    db.session.commit()

    def fetch():
        return {"data": [{"CarNo": "NEW1", "CarName": "신규"}]}, "primary"

    result = sync_engine.sync_listings(fetch=fetch, with_images=False)
    assert result["status"] == "SUCCESS"
    assert db.session.get(Listing, "OLD1").is_sold is True   # missing → sold, preserved
    assert db.session.get(Listing, "NEW1").is_sold is False
    assert SyncLog.query.filter_by(sync_type="AUTO_API_SYNC").count() == 1
