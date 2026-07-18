"""AWD(사륜구동) 정규화 — car 프로젝트와 동일 규칙."""
import re

_AWD_PATTERN = re.compile(r"(4륜구동|4WD|AWD|사륜)", re.IGNORECASE)


def normalize_awd(car_name=None, car_option=None, car_option_plus_desc=None):
    name = (car_name or "").strip()
    option = (car_option or "").strip()
    plus = (car_option_plus_desc or "").strip()
    if not name and not option and not plus:
        return "미확인"
    haystack = " ".join([name, option, plus])
    if _AWD_PATTERN.search(haystack):
        return "AWD"
    return "2WD"
