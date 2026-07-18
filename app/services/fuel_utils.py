"""유종(연료) 정규화 — car 프로젝트와 동일 규칙."""

_UNKNOWN_TOKENS = {
    "", "-", "없음", "미상", "미확인", "선택안함", "미선택", "null", "none",
}


def normalize_fuel(value):
    text = (value or "").strip()
    if not text or text.casefold() in _UNKNOWN_TOKENS:
        return "미확인"
    return text
