"""헤도닉 모델 학습·기여도·잔차 스모크."""

from app.models import AuctionRecord
from app.services.hedonic_model import HedonicModel
from tests.conftest import login


def _seed_many(db, n=40):
    rows = []
    for i in range(n):
        year = 2018 + (i % 6)
        km = 20000 + i * 1500
        rows.append(AuctionRecord(
            week_no="2026-W30",
            maker="현대" if i % 2 == 0 else "기아",
            model_name="그랜저" if i % 2 == 0 else "K5",
            car_year=year,
            car_km=km,
            fuel="가솔린" if i % 3 else "디젤",
            imported="내수",
            is_accident_free=(i % 4 != 0),
            hammer_price=1500 + (2026 - year) * -40 + (50000 - min(km, 50000)) / 200 + (80 if i % 4 else -60),
        ))
    db.session.add_all(rows)
    db.session.commit()


def test_hedonic_train_and_contributions(app, db, tmp_path):
    _seed_many(db, 45)
    path = str(tmp_path / "hedonic.pkl")
    model = HedonicModel(path=path)
    result = model.train()
    assert result["trained"] is True
    assert result["n_samples"] >= 40
    assert result["r2"] is not None

    detail = model.predict_detail(
        maker="현대", car_year=2020, car_km=35000, fuel="가솔린",
        imported="내수", is_accident_free=True, hammer_price=1800,
    )
    assert detail["ok"] is True
    assert detail["predicted_price"] > 0
    assert isinstance(detail["contributions"], list)
    assert detail["residual"] is not None
    assert detail["residual_pct"] is not None


def test_hedonic_predict_api(client, db, tmp_path, monkeypatch):
    from config import Config
    _seed_many(db, 45)
    path = str(tmp_path / "hedonic.pkl")
    monkeypatch.setattr(Config, "HEDONIC_MODEL_PATH", path)
    HedonicModel(path=path).train()
    login(client)
    resp = client.get(
        "/api/predict/hedonic"
        "?maker=현대&car_year=2020&car_km=35000&fuel=가솔린&imported=내수&accident_free=1"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["method"] == "hedonic"
    assert "contributions" in data
