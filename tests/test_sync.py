from app.extensions import db
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

    def iter_content(self, chunk_size=1024):
        import json
        yield json.dumps(self._payload).encode("utf-8")

    def close(self):
        pass


class FakeSession:
    """Primary always fails; fallback returns data."""
    def __init__(self, primary_ok=False):
        self.primary_ok = primary_ok
        self.calls = []

    def get(self, url, timeout=None, params=None, stream=False):
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
        def get(self, url, timeout=None, params=None, stream=False):
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
    assert db.session.scalar(db.select(db.func.count()).select_from(SyncLog).where(SyncLog.sync_type == "AUTO_API_SYNC")) == 1


def test_iter_listing_pages_chunks(app, monkeypatch):
    from app.services.api_client import iter_listing_pages

    class Paginated:
        def get(self, url, timeout=None, params=None, stream=False):
            page = int((params or {}).get("page", 1))
            limit = int((params or {}).get("limit", 500))
            if "carmanager" in url:
                raise RuntimeError("skip fallback")
            if page == 1:
                return FakeResp({"data": [{"CarNo": str(i)} for i in range(limit)]})
            if page == 2:
                return FakeResp({"data": [{"CarNo": str(i)} for i in range(limit, limit + 50)]})
            return FakeResp({"data": []})

    monkeypatch.setattr("app.services.api_client.Config.KS_API_BASE_URL", "https://ks.example/kindsisters")
    monkeypatch.setattr(
        "app.services.api_client.Config.FALLBACK_API_BASE_URL",
        "https://extapi.carmanager.co.kr",
    )

    pages = list(iter_listing_pages(per_page=100, session=Paginated()))
    assert len(pages) == 2
    assert len(pages[0][0]) == 100
    assert len(pages[1][0]) == 50


def test_iter_listing_pages_oversized_dump(app, monkeypatch):
    from app.services.api_client import iter_listing_pages

    class Dump:
        def get(self, url, timeout=None, params=None, stream=False):
            if "carmanager" in url:
                raise RuntimeError("skip fallback")
            return FakeResp({"data": [{"CarNo": str(i)} for i in range(250)]})

    monkeypatch.setattr("app.services.api_client.Config.KS_API_BASE_URL", "https://ks.example/kindsisters")
    monkeypatch.setattr("app.services.api_client.Config.FALLBACK_API_BASE_URL", "")

    pages = list(iter_listing_pages(per_page=100, session=Dump()))
    assert [len(p[0]) for p in pages] == [100, 100, 50]
