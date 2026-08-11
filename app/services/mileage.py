"""주행거리 15,000km 단위 구간화 (PRD §5.2)."""
import math

from config import Config
from app.services.analysis_logic import get_params


def calculate_mileage_bin(mileage, step=None, cap=None):
    if step is None or cap is None:
        p = get_params(
            "mileage.km_bin",
            {"step": Config.KM_BUCKET_STEP, "max": Config.KM_BUCKET_MAX},
        )
        step = step if step is not None else p["step"]
        cap = cap if cap is not None else p["max"]
    if mileage is None:
        return "미상"
    try:
        km = float(mileage)
    except (TypeError, ValueError):
        return "미상"
    if km != km:  # NaN
        return "미상"
    if km < 0:
        return "미상"
    if km >= cap:
        return f"{cap // 10000}만km 이상"
    low = int(math.floor(km / step) * step)
    high = low + step
    return f"{low / 10000:g}만~{high / 10000:g}만km"
