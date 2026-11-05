"""사고등급·무사고 판정 (사고A상세 + XX교환 + W판금).

저장·표시 형식: A-무사고 / B-단순교환 / C-외판교환 / D-외판판금 / E-골격판금 / F-기타.
"""
import pandas as pd

GRADE_CLEAN = "무사고"
GRADE_SIMPLE = "단순교환"
GRADE_FRAME = "골격판금"
GRADE_PANEL = "외판판금"
GRADE_EXCHANGE = "외판교환"
GRADE_UNKNOWN = "기타"

# 알파벳 접두 (엑셀 평가등급 AA/AB와 별개)
GRADE_CODE = {
    GRADE_CLEAN: "A",
    GRADE_SIMPLE: "B",
    GRADE_EXCHANGE: "C",
    GRADE_PANEL: "D",
    GRADE_FRAME: "E",
    GRADE_UNKNOWN: "F",
}


def _labeled(grade: str) -> str:
    code = GRADE_CODE.get(grade, "F")
    return f"{code}-{grade}"


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
    accident_grade는 A-무사고 형태.
    """
    detail = _detail_text(accident_detail)
    xx_empty = _is_zeroish(xx_exchange)
    w_empty = _is_zeroish(w_panel)

    if detail == GRADE_CLEAN or (not detail and xx_empty and w_empty):
        return _labeled(GRADE_CLEAN), True
    if "골격" in detail:
        return _labeled(GRADE_FRAME), False
    if "단순" in detail or detail in ("교환", "단순교환"):
        return _labeled(GRADE_SIMPLE), False
    if not w_empty:
        return _labeled(GRADE_PANEL), False
    if not xx_empty:
        return _labeled(GRADE_EXCHANGE), False
    if detail:
        return _labeled(GRADE_UNKNOWN), False
    return _labeled(GRADE_UNKNOWN), False


def is_accident_free(accident_detail, xx_exchange, w_panel) -> bool:
    """하위 호환 — 무사고 여부만."""
    return classify_accident(accident_detail, xx_exchange, w_panel)[1]
