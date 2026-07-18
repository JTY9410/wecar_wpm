from app.models import AuctionRecord
from app.services.price_model import PriceModel
from app.extensions import db as _db


def _seed_records(db, n=20):
    for i in range(n):
        db.session.add(AuctionRecord(
            week_no="2026-W29", maker="현대", car_name=f"차{i%3}",
            car_year=2015 + (i % 8), car_km=10000 * (i % 10),
            fuel="가솔린", imported="수출", hammer_price=300 + i * 10,
            is_accident_free=True, car_code="c"))
    db.session.commit()


def test_train_and_predict(app, db, tmp_path):
    _seed_records(db)
    model = PriceModel(path=str(tmp_path / "m.pkl"))
    res = model.train()
    assert res["trained"] is True
    price = model.predict(maker="현대", car_year=2018, car_km=50000, imported="수출")
    assert isinstance(price, float)
    assert price > 0


def test_predict_without_model(app, db, tmp_path):
    model = PriceModel(path=str(tmp_path / "missing.pkl"))
    assert model.predict("현대", 2018, 50000, "수출") is None


def test_insufficient_data(app, db, tmp_path):
    model = PriceModel(path=str(tmp_path / "m.pkl"))
    res = model.train()
    assert res["trained"] is False
