"""car1/car2 차량코드·명칭 → car1 vehicle_* PK 해석 (read-only)."""

from __future__ import annotations

import re

from app.extensions import db
from app.models import (
    VehicleCodeMapping,
    VehicleGrade,
    VehicleGradeDetail,
    VehicleMaker,
    VehicleModel,
    VehicleModelDetail,
)

_NULLISH = {"", "null", "none", "없음", "-"}
_JACCARD_MIN = 0.85
_PARTS = ("maker", "model", "mdetail", "grade", "gdetail")

_MAKER_ALIASES = {
    "쌍용": "KG모빌리티(쌍용)", "KG모빌리티": "KG모빌리티(쌍용)",
    "삼성": "르노코리아(삼성)", "르노삼성": "르노코리아(삼성)", "르노코리아": "르노코리아(삼성)",
    "GM대우": "쉐보레", "대우": "쉐보레", "한국GM": "쉐보레",
    "현대자동차": "현대", "기아자동차": "기아", "기아차": "기아",
}

_FUEL_SYNONYMS: dict[str, set[str]] = {
    "경유": {"경유", "디젤", "diesel"}, "디젤": {"경유", "디젤", "diesel"},
    "가솔린": {"가솔린", "휘발유", "gasoline", "petrol"},
    "휘발유": {"가솔린", "휘발유", "gasoline", "petrol"},
    "전기": {"전기", "ev", "electric"}, "하이브리드": {"하이브리드", "hev", "hybrid"},
    "LPG": {"lpg", "엘피지", "lpgi"}, "수소": {"수소", "fcev"},
}

_LEVELS: tuple[tuple[str, type, str, str, str | None], ...] = (
    ("maker", VehicleMaker, "maker_no", "maker_name", None),
    ("model", VehicleModel, "model_no", "model_name", "maker_no"),
    ("mdetail", VehicleModelDetail, "mdetail_no", "mdetail_name", "model_no"),
    ("grade", VehicleGrade, "grade_no", "grade_name", "mdetail_no"),
    ("gdetail", VehicleGradeDetail, "gdetail_no", "gdetail_name", "grade_no"),
)


def _clean(value: str | None) -> str:
    text = (value or "").strip()
    return "" if text.lower() in _NULLISH else text


def normalize_label(value: str | None) -> str:
    """괄호·구동방식 등 API 부가표기를 제거한 비교용 라벨."""
    text = _clean(value)
    if not text:
        return ""
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"（[^）]*）", " ", text)
    text = re.sub(r"(?i)\b(FWD|AWD|4WD|2WD|4x4|4×4|WD)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: str | None) -> set[str]:
    text = normalize_label(value).casefold()
    if not text:
        return set()
    out: set[str] = set()
    for part in re.findall(r"[a-z0-9.]+|[가-힣]+", text):
        out.add(part)
        for syns in _FUEL_SYNONYMS.values():
            if part in {s.casefold() for s in syns}:
                out |= {s.casefold() for s in syns}
    return out


def _empty_result() -> dict:
    out = {f"{p}_no": None for p in _PARTS}
    out.update({f"{p}_name": None for p in _PARTS})
    out.update(car2={}, match_level=None, unresolved=[])
    return out


def _map_code(level: str, code: str) -> VehicleCodeMapping | None:
    return db.session.execute(
        db.select(VehicleCodeMapping).where(
            VehicleCodeMapping.level == level,
            VehicleCodeMapping.car2_code == code,
            VehicleCodeMapping.status == "confirmed",
        )
    ).scalar_one_or_none()


def _rows_for_level(model: type, parent_attr: str | None, parent_code: str | None) -> list:
    stmt = db.select(model)
    if parent_attr and parent_code:
        stmt = stmt.where(getattr(model, parent_attr) == parent_code)
    return list(db.session.execute(stmt).scalars().all())


def _match_name(
    level: str, name: str, *, model: type, name_attr: str, pk_attr: str,
    parent_attr: str | None, parent_code: str | None,
) -> tuple[str | None, str | None]:
    raw = _clean(name)
    if not raw:
        return None, None
    query = _MAKER_ALIASES.get(raw, raw) if level == "maker" else raw
    rows = _rows_for_level(model, parent_attr, parent_code)
    norm_query = normalize_label(query)
    for row in rows:
        row_name = getattr(row, name_attr)
        if normalize_label(row_name) == norm_query or _clean(row_name) == query:
            return getattr(row, pk_attr), row_name
    qt = _tokens(query)
    best_row, best_score = None, 0.0
    for row in rows:
        rt = _tokens(getattr(row, name_attr))
        score = len(qt & rt) / len(qt | rt) if qt and rt else 0.0
        if score > best_score:
            best_score, best_row = score, row
    if best_row and best_score >= _JACCARD_MIN:
        return getattr(best_row, pk_attr), getattr(best_row, name_attr)
    return None, None


def _resolve_level(
    level: str, *, model: type, pk_attr: str, name_attr: str,
    parent_attr: str | None, parent_code: str | None,
    code: str | None, name: str | None,
) -> tuple[str | None, str | None, str | None]:
    code, name = _clean(code), _clean(name)
    if code:
        row = db.session.get(model, code)
        if row:
            return code, getattr(row, name_attr), None
        mapping = _map_code(level, code)
        if mapping and (mapped := db.session.get(model, mapping.car1_code)):
            return mapping.car1_code, getattr(mapped, name_attr), code
    if name:
        pk, row_name = _match_name(
            level, name, model=model, name_attr=name_attr, pk_attr=pk_attr,
            parent_attr=parent_attr, parent_code=parent_code,
        )
        if pk:
            return pk, row_name, None
    return None, None, None


def resolve_vehicle_codes(
    *,
    maker_no: str | None = None, model_no: str | None = None,
    mdetail_no: str | None = None, grade_no: str | None = None,
    gdetail_no: str | None = None, maker: str | None = None,
    model: str | None = None, mdetail: str | None = None,
    grade: str | None = None, gdetail: str | None = None,
) -> dict:
    inputs = {
        "maker": (maker_no, maker), "model": (model_no, model),
        "mdetail": (mdetail_no, mdetail), "grade": (grade_no, grade),
        "gdetail": (gdetail_no, gdetail),
    }
    out = _empty_result()
    car2: dict[str, str] = {}
    unresolved: list[str] = []
    parent_code: str | None = None
    for level, model_cls, pk_attr, name_attr, parent_attr in _LEVELS:
        code_in, name_in = inputs[level]
        if not code_in and not name_in:
            break
        if parent_attr and not parent_code:
            unresolved.append(level)
            break
        pk, row_name, car2_code = _resolve_level(
            level, model=model_cls, pk_attr=pk_attr, name_attr=name_attr,
            parent_attr=parent_attr, parent_code=parent_code,
            code=code_in, name=name_in,
        )
        if not pk:
            unresolved.append(level)
            break
        out[pk_attr], out[name_attr], out["match_level"] = pk, row_name, level
        parent_code = pk
        if car2_code:
            car2[pk_attr] = car2_code
    out["car2"], out["unresolved"] = car2, unresolved
    return out
