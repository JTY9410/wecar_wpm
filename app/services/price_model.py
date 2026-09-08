"""Tier 1 로컬 무료 ML 예측 (PRD §5.6): RandomForestRegressor."""
import os

import joblib
import numpy as np

from config import Config
from app.models import AuctionRecord
from app.services.analysis_logic import is_active

FEATURES = ["maker", "car_year", "car_km", "imported"]


class PriceModel:
    def __init__(self, path=None):
        self.path = path or Config.MODEL_PATH
        self.model = None
        self.encoders = None

    def _encode(self, rows, fit=False):
        import pandas as pd
        df = pd.DataFrame(rows)
        if self.encoders is None or fit:
            self.encoders = {}
        X = []
        for col in ["maker", "imported"]:
            vals = df[col].fillna("").astype(str)
            if fit:
                cats = {v: i for i, v in enumerate(sorted(vals.unique()))}
                self.encoders[col] = cats
            cats = self.encoders.get(col, {})
            df[col] = vals.map(lambda v: cats.get(v, -1))
        df["car_year"] = df["car_year"].fillna(0).astype(float)
        df["car_km"] = df["car_km"].fillna(0).astype(float)
        return df[FEATURES].to_numpy()

    def train(self):
        from app.services.training import training_allowed
        if not training_allowed():
            return {"trained": False, "reason": "serving_only"}
        if not is_active("predict.random_forest"):
            return {"trained": False, "reason": "inactive"}
        from sklearn.ensemble import RandomForestRegressor
        from app.extensions import db
        recs = db.session.execute(db.select(AuctionRecord).where(AuctionRecord.hammer_price.isnot(None))).scalars().all()
        if len(recs) < 5:
            return {"trained": False, "reason": "insufficient_data", "count": len(recs)}
        rows = [{"maker": r.maker, "car_year": r.car_year, "car_km": r.car_km,
                 "imported": r.imported} for r in recs]
        y = np.array([r.hammer_price for r in recs], dtype=float)
        X = self._encode(rows, fit=True)
        model = RandomForestRegressor(n_estimators=120, random_state=42)
        model.fit(X, y)
        self.model = model
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        joblib.dump({"model": model, "encoders": self.encoders}, self.path)
        return {"trained": True, "count": len(recs)}

    def load(self):
        if not os.path.exists(self.path):
            return False
        blob = joblib.load(self.path)
        self.model = blob["model"]
        self.encoders = blob["encoders"]
        return True

    def predict(self, maker, car_year, car_km, imported):
        if not is_active("predict.random_forest"):
            return None
        if self.model is None and not self.load():
            return None
        X = self._encode([{"maker": maker, "car_year": car_year,
                           "car_km": car_km, "imported": imported}])
        return float(self.model.predict(X)[0])
