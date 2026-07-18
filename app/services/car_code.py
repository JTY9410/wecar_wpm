"""카코드 체계 (car 계층 참조).

차원: 제조사 → 모델 → 상세모델 → 등급 → 상세등급 → 년식 → 유종 → AWD
복합 키 car_code 로 저장하여 car 소매시세 연동 시 도매 시세를 쉽게 조회.
"""
import hashlib
import re

from app.services.awd_utils import normalize_awd
from app.services.fuel_utils import normalize_fuel


def slug(text):
    if text is None:
        return ""
    s = re.sub(r"[\s\W_]+", "", str(text)).lower()
    return s or "unknown"


def build_car_code(
    maker=None,
    model=None,
    mdetail=None,
    grade=None,
    gdetail=None,
    car_year=None,
    fuel=None,
    awd=None,
    car_name=None,
    car_option=None,
):
    """파이프 결합 카코드. car 소매 연동용 안정 키."""
    fuel_n = normalize_fuel(fuel)
    if awd in ("AWD", "2WD", "미확인"):
        awd_n = awd
    else:
        awd_n = normalize_awd(car_name or gdetail or mdetail, car_option, None)
    parts = [
        slug(maker),
        slug(model),
        slug(mdetail),
        slug(grade),
        slug(gdetail),
        str(int(car_year) if car_year not in (None, "") else 0),
        slug(fuel_n),
        slug(awd_n),
    ]
    return "|".join(parts)


def car_code_hash(car_code):
    return hashlib.sha1(car_code.encode("utf-8")).hexdigest()[:16]


def parse_car_code(car_code):
    parts = (car_code or "").split("|")
    keys = ["maker", "model", "mdetail", "grade", "gdetail", "car_year", "fuel", "awd"]
    out = {k: None for k in keys}
    for i, k in enumerate(keys):
        if i < len(parts):
            out[k] = parts[i] or None
    if out.get("car_year"):
        try:
            out["car_year"] = int(out["car_year"])
        except ValueError:
            out["car_year"] = None
    return out
