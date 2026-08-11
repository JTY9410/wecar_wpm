"""Analysis logic registry — built-in seed, CRUD, runtime params/active lookup."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from app.models import AnalysisLogic

BUILTIN_SPECS: list[dict[str, Any]] = [
    {
        "code": "mileage.km_bin",
        "name": "KM구간",
        "description": "경매 주행거리를 km 구간(step/max)으로 분류합니다.",
        "category": "ingest",
        "default_params": {"step": 15000, "max": 200000},
        "sort_order": 10,
    },
    {
        "code": "aggregate.market_summary",
        "name": "시장요약 집계",
        "description": "주차별 MarketSummary 재집계를 수행합니다.",
        "category": "aggregate",
        "default_params": {},
        "sort_order": 20,
    },
    {
        "code": "predict.random_forest",
        "name": "랜덤포레스트 예측",
        "description": "낙찰가 랜덤포레스트 학습·예측을 수행합니다.",
        "category": "predict",
        "default_params": {},
        "sort_order": 30,
    },
    {
        "code": "predict.hedonic",
        "name": "헤도닉 예측",
        "description": "헤도닉 회귀 학습·예측을 수행합니다.",
        "category": "predict",
        "default_params": {},
        "sort_order": 40,
    },
    {
        "code": "briefing.price_alert",
        "name": "가격 변동 알림",
        "description": "전주 대비 낙찰가 변동률이 임계치를 넘으면 브리핑에 표시합니다.",
        "category": "briefing",
        "default_params": {"threshold_pct": 5.0, "min_samples": 2},
        "sort_order": 50,
    },
    {
        "code": "briefing.surge_alert",
        "name": "급등 알림",
        "description": "표본 수 급증 시 브리핑에 표시합니다.",
        "category": "briefing",
        "default_params": {"threshold_pct": 30.0},
        "sort_order": 60,
    },
    {
        "code": "briefing.hedonic_residual",
        "name": "헤도닉 잔차 알림",
        "description": "헤도닉 잔차가 임계치를 넘으면 브리핑에 표시합니다.",
        "category": "briefing",
        "default_params": {"threshold_pct": 15.0},
        "sort_order": 70,
    },
]

_BUILTIN_DEFAULTS = {spec["code"]: spec["default_params"] for spec in BUILTIN_SPECS}


def _spec_for_code(code: str) -> dict[str, Any] | None:
    for spec in BUILTIN_SPECS:
        if spec["code"] == code:
            return spec
    return None


def _get_row(code: str) -> AnalysisLogic | None:
    return db.session.execute(
        select(AnalysisLogic).where(AnalysisLogic.code == code)
    ).scalar_one_or_none()


def seed_builtin_logics() -> int:
    """Insert missing built-ins; refresh name/description/sort only if present."""
    created = 0
    for spec in BUILTIN_SPECS:
        row = _get_row(spec["code"])
        if row is None:
            db.session.add(
                AnalysisLogic(
                    code=spec["code"],
                    name=spec["name"],
                    description=spec["description"],
                    category=spec["category"],
                    is_builtin=True,
                    is_active=True,
                    params=dict(spec["default_params"]),
                    sort_order=spec["sort_order"],
                )
            )
            created += 1
        else:
            row.name = spec["name"]
            row.description = spec["description"]
            row.sort_order = spec["sort_order"]
    if created:
        db.session.commit()
    elif db.session.dirty:
        db.session.commit()
    return created


def is_active(code: str) -> bool:
    row = _get_row(code)
    if row is None:
        return True
    return bool(row.is_active)


def get_params(code: str, defaults: dict | None = None) -> dict:
    base = dict(defaults or _BUILTIN_DEFAULTS.get(code, {}))
    row = _get_row(code)
    if row is None:
        return base
    merged = {**base, **(row.params or {})}
    return merged


def list_logics(category: str | None = None) -> list[AnalysisLogic]:
    stmt = select(AnalysisLogic).order_by(AnalysisLogic.sort_order, AnalysisLogic.code)
    if category:
        stmt = stmt.where(AnalysisLogic.category == category)
    return list(db.session.execute(stmt).scalars().all())


def upsert(
    *,
    code: str,
    name: str,
    description: str | None,
    category: str,
    params: dict,
    is_active: bool,
    is_builtin: bool = False,
    updated_by: str | None = None,
) -> AnalysisLogic:
    validated = validate_params(code, params)
    row = _get_row(code)
    if row is None:
        row = AnalysisLogic(code=code)
        db.session.add(row)
    row.name = name
    row.description = description
    row.category = category
    row.params = validated
    row.is_active = is_active
    row.is_builtin = is_builtin
    row.updated_by = updated_by
    db.session.commit()
    return row


def set_active(logic_id: int, active: bool) -> AnalysisLogic | None:
    row = db.session.get(AnalysisLogic, logic_id)
    if row is None:
        return None
    row.is_active = active
    db.session.commit()
    return row


def delete_logic(logic_id: int) -> tuple[bool, str]:
    row = db.session.get(AnalysisLogic, logic_id)
    if row is None:
        return False, "not found"
    if row.is_builtin:
        return False, "built-in logic cannot be deleted"
    db.session.delete(row)
    db.session.commit()
    return True, ""


def _validate_km_bin(params: dict) -> dict:
    step = params.get("step")
    max_km = params.get("max")
    if not isinstance(step, int) or step < 1000 or step > 100_000:
        raise ValueError("step must be an integer between 1000 and 100000")
    if not isinstance(max_km, int) or max_km < 10_000 or max_km > 1_000_000:
        raise ValueError("max must be an integer between 10000 and 1000000")
    return {"step": step, "max": max_km}


def _validate_threshold_pct(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    pct = float(value)
    if pct < 0 or pct > 100:
        raise ValueError(f"{field} must be between 0 and 100")
    return pct


def _validate_min_samples(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 100:
        raise ValueError("min_samples must be an integer between 1 and 100")
    return value


def validate_params(code: str, params: dict) -> dict:
    """Validate and normalize params for a logic code. Raises ValueError on invalid input."""
    if code == "mileage.km_bin":
        return _validate_km_bin(params)
    if code in ("aggregate.market_summary", "predict.random_forest", "predict.hedonic"):
        if params:
            raise ValueError("params must be empty for this logic")
        return {}
    if code == "briefing.price_alert":
        return {
            "threshold_pct": _validate_threshold_pct(
                params.get("threshold_pct"), field="threshold_pct"
            ),
            "min_samples": _validate_min_samples(params.get("min_samples")),
        }
    if code in ("briefing.surge_alert", "briefing.hedonic_residual"):
        return {
            "threshold_pct": _validate_threshold_pct(
                params.get("threshold_pct"), field="threshold_pct"
            ),
        }
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    return dict(params)
