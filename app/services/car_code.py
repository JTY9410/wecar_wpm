"""카코드 체계 (car 계층 참조).

차원은 각각 별도 컬럼에 저장한다:
  제조사 · 모델 · 상세모델 · 등급 · 상세등급 · 년식 · 유종 · AWD · 사고여부

car_code 는 API 조회용 짧은 해시 키이며, 전체 텍스트를 한 열에 넣지 않는다.
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


def extract_grade_gdetail(maker=None, model=None, mdetail=None, car_name=None):
    """차명에서 등급·세부등급을 분리. 원문은 세부등급, 끝 토큰은 등급."""
    raw = str(car_name or "").strip()
    if not raw:
        return "기본", "기본"
    remainder = raw
    for part in (maker, mdetail, model):
        if not part:
            continue
        p = str(part).strip()
        if not p:
            continue
        if remainder.startswith(p):
            remainder = remainder[len(p):].strip()
        elif p in remainder:
            remainder = remainder.replace(p, "", 1).strip()
    remainder = re.sub(r"\s+", " ", remainder).strip(" -/|")
    if not remainder:
        base = str(mdetail or model or "기본").strip() or "기본"
        return "기본", base
    tokens = remainder.split()
    if len(tokens) == 1:
        return tokens[0], tokens[0]
    return tokens[-1], remainder


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
    accident_free=None,
):
    """계층 차원 기반 짧은 해시 카코드 (표시용 전체 문자열 아님)."""
    fuel_n = normalize_fuel(fuel)
    if awd in ("AWD", "2WD", "미확인"):
        awd_n = awd
    else:
        awd_n = normalize_awd(car_name or gdetail or mdetail, car_option, None)
    acc = "1" if accident_free else "0" if accident_free is not None else "x"
    parts = [
        slug(maker),
        slug(model),
        slug(mdetail),
        slug(grade),
        slug(gdetail),
        str(int(car_year) if car_year not in (None, "") else 0),
        slug(fuel_n),
        slug(awd_n),
        acc,
    ]
    return car_code_hash("|".join(parts))


def car_code_hash(car_code):
    return hashlib.sha1(str(car_code).encode("utf-8")).hexdigest()[:16]


def parse_car_code(car_code):
    """해시 카코드는 역파싱 불가 — 차원은 DB 컬럼을 사용."""
    return {
        "maker": None, "model": None, "mdetail": None, "grade": None,
        "gdetail": None, "car_year": None, "fuel": None, "awd": None,
        "car_code": car_code,
    }
