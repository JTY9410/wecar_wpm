"""헤도닉(hedonic) 낙찰가 분해·예측.

log(hammer) ~ 연식·주행·연료·사고·수입·제작사 등 속성.
Ridge로 학습해 속성별 기여도(만원)와 잔차를 제공한다.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import joblib
import numpy as np

from config import Config
from app.models import AuctionRecord
from app.services.analysis_logic import is_active

NUMERIC = ("car_year", "car_km", "log_km", "age_proxy")
CATEGORICAL = ("maker", "fuel", "imported", "is_accident_free")


class HedonicModel:
    def __init__(self, path=None):
        self.path = path or Config.HEDONIC_MODEL_PATH
        self.pipeline = None
        self.feature_names_ = []
        self.meta_ = {}

    def _rows_from_records(self, recs):
        rows, y = [], []
        for r in recs:
            if r.hammer_price is None or r.hammer_price <= 0:
                continue
            year = int(r.car_year or 0)
            km = float(r.car_km or 0)
            rows.append({
                "car_year": year,
                "car_km": km,
                "log_km": float(np.log1p(max(km, 0))),
                "age_proxy": float(max(0, 2026 - year)) if year else 0.0,
                "maker": (r.maker or "unknown").strip() or "unknown",
                "fuel": (r.fuel or "unknown").strip() or "unknown",
                "imported": (r.imported or "unknown").strip() or "unknown",
                "is_accident_free": "Y" if r.is_accident_free else "N",
            })
            y.append(float(r.hammer_price))
        return rows, y

    def _build_pipeline(self):
        from sklearn.compose import ColumnTransformer
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler

        pre = ColumnTransformer(
            transformers=[
                ("num", StandardScaler(), list(NUMERIC)),
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False, min_frequency=2),
                    list(CATEGORICAL),
                ),
            ]
        )
        return Pipeline([
            ("pre", pre),
            ("model", Ridge(alpha=2.0, random_state=42)),
        ])

    def _feature_names(self, pipeline):
        pre = pipeline.named_steps["pre"]
        names = list(NUMERIC)
        try:
            cat = pre.named_transformers_["cat"]
            names.extend(cat.get_feature_names_out(list(CATEGORICAL)).tolist())
        except Exception:
            pass
        return names

    def train(self):
        from app.services.training import training_allowed
        if not training_allowed():
            return {"trained": False, "reason": "serving_only"}
        if not is_active("predict.hedonic"):
            return {"trained": False, "reason": "inactive"}
        from app.extensions import db
        recs = db.session.execute(db.select(AuctionRecord).where(
            AuctionRecord.hammer_price.isnot(None),
            AuctionRecord.hammer_price > 0,
        )).scalars().all()
        rows, y = self._rows_from_records(recs)
        if len(rows) < 30:
            return {"trained": False, "reason": "insufficient_data", "count": len(rows)}

        import pandas as pd
        from sklearn.metrics import r2_score

        df = pd.DataFrame(rows)
        y = np.asarray(y, dtype=float)
        y_log = np.log(y)

        pipe = self._build_pipeline()
        pipe.fit(df, y_log)
        pred = np.exp(pipe.predict(df))
        r2 = float(r2_score(y, pred))

        self.pipeline = pipe
        self.feature_names_ = self._feature_names(pipe)
        self.meta_ = {
            "n_samples": len(rows),
            "r2": round(r2, 4),
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "method": "hedonic_ridge_log",
        }
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        joblib.dump(
            {
                "pipeline": pipe,
                "feature_names": self.feature_names_,
                "meta": self.meta_,
            },
            self.path,
        )
        return {"trained": True, **self.meta_}

    def load(self):
        if not os.path.exists(self.path):
            return False
        try:
            blob = joblib.load(self.path)
            self.pipeline = blob["pipeline"]
            self.feature_names_ = blob.get("feature_names") or []
            self.meta_ = blob.get("meta") or {}
            return True
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("hedonic model load failed: %s", exc)
            self.pipeline = None
            return False

    def _frame(self, attrs: dict):
        import pandas as pd

        year = int(attrs.get("car_year") or 0)
        km = float(attrs.get("car_km") or 0)
        row = {
            "car_year": year,
            "car_km": km,
            "log_km": float(np.log1p(max(km, 0))),
            "age_proxy": float(max(0, 2026 - year)) if year else 0.0,
            "maker": (attrs.get("maker") or "unknown").strip() or "unknown",
            "fuel": (attrs.get("fuel") or "unknown").strip() or "unknown",
            "imported": (attrs.get("imported") or "unknown").strip() or "unknown",
            "is_accident_free": "Y" if attrs.get("is_accident_free") in (True, "Y", "1", 1) else "N",
        }
        return pd.DataFrame([row]), row

    def predict_detail(self, **attrs):
        if not is_active("predict.hedonic"):
            return None
        if self.pipeline is None and not self.load():
            return None
        df, row = self._frame(attrs)
        pred_log = float(self.pipeline.predict(df)[0])
        predicted = float(np.exp(pred_log))
        contributions = self._contributions(df)
        out = {
            "ok": True,
            "method": "hedonic",
            "predicted_price": round(predicted, 1),
            "contributions": contributions,
            "meta": self.meta_,
            "inputs": row,
        }
        actual = attrs.get("hammer_price")
        if actual is not None:
            try:
                actual_f = float(actual)
                residual = actual_f - predicted
                residual_pct = (residual / predicted * 100.0) if predicted else None
                out["actual_price"] = round(actual_f, 1)
                out["residual"] = round(residual, 1)
                out["residual_pct"] = round(residual_pct, 1) if residual_pct is not None else None
            except (TypeError, ValueError):
                pass
        return out

    def _contributions(self, df):
        """Leave-one-out style contribution in price (만원) space."""
        pre = self.pipeline.named_steps["pre"]
        model = self.pipeline.named_steps["model"]
        X = np.asarray(pre.transform(df), dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        coef = np.asarray(model.coef_, dtype=float).ravel()
        intercept = float(model.intercept_)
        full_log = intercept + float(np.dot(X[0], coef))
        names = self.feature_names_ or [f"f{i}" for i in range(X.shape[1])]
        out = []
        for i, name in enumerate(names[: X.shape[1]]):
            without = full_log - float(coef[i] * X[0, i])
            delta = float(np.exp(full_log) - np.exp(without))
            if abs(delta) < 0.05:
                continue
            out.append({
                "feature": name,
                "label": _humanize_feature(name),
                "contribution": round(delta, 1),
            })
        out.sort(key=lambda x: -abs(x["contribution"]))
        return out[:12]

    def status(self):
        if self.pipeline is None:
            self.load()
        return {
            "available": self.pipeline is not None,
            "path": self.path,
            **(self.meta_ or {}),
        }


def _humanize_feature(name: str) -> str:
    mapping = {
        "car_year": "연식",
        "car_km": "주행거리",
        "log_km": "주행거리(로그)",
        "age_proxy": "차령",
    }
    if name in mapping:
        return mapping[name]
    if name.startswith("maker_"):
        return f"제작사:{name.split('_', 1)[-1]}"
    if name.startswith("fuel_"):
        return f"연료:{name.split('_', 1)[-1]}"
    if name.startswith("imported_"):
        return f"구분:{name.split('_', 1)[-1]}"
    if name.startswith("is_accident_free_"):
        return "무사고" if name.endswith("_Y") else "사고이력"
    return name
