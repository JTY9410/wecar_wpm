"""무사고 판정 (PRD §5.3)."""
import pandas as pd


def _is_zeroish(val):
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    s = str(val).strip()
    return s in ("", "0", "nan", "None")


def is_accident_free(accident_detail, xx_exchange, w_panel):
    """무사고 상세이거나 교환/판금 이력이 모두 0/NaN이면 무사고."""
    if accident_detail is not None and str(accident_detail).strip() == "무사고":
        return True
    return _is_zeroish(xx_exchange) and _is_zeroish(w_panel)
