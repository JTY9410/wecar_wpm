"""사고등급·무사고 판정 (사고A상세 + XX교환 + W판금)."""
import pandas as pd

GRADE_CLEAN = "무사고"
GRADE_SIMPLE = "단순교환"
GRADE_FRAME = "골격판금"
GRADE_PANEL = "외판판금"
GRADE_EXCHANGE = "외판교환"
GRADE_UNKNOWN = "사고"


def _is_zeroish(val):
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    s = str(val).strip()
    return s in ("", "0", "nan", "None", "-", "없음")


def _detail_text(accident_detail) -> str:
    if accident_detail is None:
        return ""
    if isinstance(accident_detail, float) and pd.isna(accident_detail):
        return ""
    return str(accident_detail).strip()


def classify_accident(accident_detail, xx_exchange, w_panel) -> tuple[str, bool]:
    """(accident_grade, is_accident_free).

    우선순위: 무사고 → 골격판금 → 단순교환 → 외판판금(W) → 외판교환(XX) → 기타.
    """
    detail = _detail_text(accident_detail)
    xx_empty = _is_zeroish(xx_exchange)
    w_empty = _is_zeroish(w_panel)

    if detail == GRADE_CLEAN or (not detail and xx_empty and w_empty):
        return GRADE_CLEAN, True
    if "골격" in detail:
        return GRADE_FRAME, False
    if "단순" in detail or detail in ("교환", "단순교환"):
        return GRADE_SIMPLE, False
    if not w_empty:
        return GRADE_PANEL, False
    if not xx_empty:
        return GRADE_EXCHANGE, False
    if detail:
        return detail[:40], False
    return GRADE_UNKNOWN, False


def is_accident_free(accident_detail, xx_exchange, w_panel) -> bool:
    """하위 호환 — 무사고 여부만."""
    return classify_accident(accident_detail, xx_exchange, w_panel)[1]
