"""car2 코드 계층 → car1 VehicleCodeMapping 후보 동기화 및 CSV import/export."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

import requests
from flask import current_app

from app.extensions import db
from app.models import (
    VehicleCodeMapping,
    VehicleGrade,
    VehicleGradeDetail,
    VehicleMaker,
    VehicleModel,
    VehicleModelDetail,
)
from app.services.code_resolve import normalize_label

_TIMEOUT = 15
_JACCARD_MIN = 0.85
_STATUSES = frozenset({"candidate", "confirmed", "rejected"})
_PROTECTED = frozenset({"confirmed", "rejected"})

_MAKER_ALIASES = {
    "쌍용": "KG모빌리티(쌍용)",
    "KG모빌리티": "KG모빌리티(쌍용)",
    "삼성": "르노코리아(삼성)",
    "르노삼성": "르노코리아(삼성)",
    "르노코리아": "르노코리아(삼성)",
    "GM대우": "쉐보레",
    "대우": "쉐보레",
    "한국GM": "쉐보레",
    "현대자동차": "현대",
    "기아자동차": "기아",
    "기아차": "기아",
}

_CSV_HEADER = ("level", "car2_code", "car1_code", "car2_name", "car1_name")


def _clean(value: str | None) -> str:
    text = (value or "").strip()
    return "" if text.lower() in {"", "null", "none", "없음", "-"} else text


def _tokens(value: str | None) -> set[str]:
    text = normalize_label(value).casefold()
    if not text:
        return set()
    return set(re.findall(r"[a-z0-9.]+|[가-힣]+", text))


def _rows_for_level(
    model: type, parent_attr: str | None, parent_code: str | None
) -> list:
    stmt = db.select(model)
    if parent_attr and parent_code:
        stmt = stmt.where(getattr(model, parent_attr) == parent_code)
    return list(db.session.execute(stmt).scalars().all())


def _match_car1_name(
    level: str,
    name: str,
    *,
    model: type,
    pk_attr: str,
    name_attr: str,
    parent_attr: str | None,
    parent_code: str | None,
) -> tuple[str | None, str | None, float | None]:
    raw = _clean(name)
    if not raw:
        return None, None, None
    query = _MAKER_ALIASES.get(raw, raw) if level == "maker" else raw
    rows = _rows_for_level(model, parent_attr, parent_code)
    norm_query = normalize_label(query)
    for row in rows:
        row_name = getattr(row, name_attr)
        if normalize_label(row_name) == norm_query or _clean(row_name) == query:
            return getattr(row, pk_attr), row_name, 1.0
    qt = _tokens(query)
    best_row, best_score = None, 0.0
    for row in rows:
        rt = _tokens(getattr(row, name_attr))
        score = len(qt & rt) / len(qt | rt) if qt and rt else 0.0
        if score > best_score:
            best_score, best_row = score, row
    if best_row and best_score >= _JACCARD_MIN:
        return getattr(best_row, pk_attr), getattr(best_row, name_attr), best_score
    return None, None, None


def _fetch_items(base_url: str, path: str, params: dict[str, str] | None = None) -> list[dict]:
    url = f"{base_url.rstrip('/')}{path}"
    resp = requests.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items") or []
    return []


def _get_mapping(level: str, car2_code: str) -> VehicleCodeMapping | None:
    return db.session.execute(
        db.select(VehicleCodeMapping).where(
            VehicleCodeMapping.level == level,
            VehicleCodeMapping.car2_code == car2_code,
        )
    ).scalar_one_or_none()


def _confirmed_car1_conflict(
    level: str, car1_code: str, *, exclude_car2: str | None = None
) -> VehicleCodeMapping | None:
    stmt = db.select(VehicleCodeMapping).where(
        VehicleCodeMapping.level == level,
        VehicleCodeMapping.car1_code == car1_code,
        VehicleCodeMapping.status == "confirmed",
    )
    if exclude_car2:
        stmt = stmt.where(VehicleCodeMapping.car2_code != exclude_car2)
    return db.session.execute(stmt).scalar_one_or_none()


def confirmed_car1_conflict(
    level: str, car1_code: str, *, exclude_car2: str | None = None
) -> VehicleCodeMapping | None:
    return _confirmed_car1_conflict(level, car1_code, exclude_car2=exclude_car2)


def _upsert_candidate(
    level: str,
    car2_code: str,
    car1_code: str,
    car2_name: str | None,
    car1_name: str | None,
    match_score: float | None,
) -> tuple[int, int]:
    """Returns (created, skipped) counts."""
    existing = _get_mapping(level, car2_code)
    if existing:
        if existing.status in _PROTECTED:
            return 0, 1
        existing.car1_code = car1_code
        existing.car2_name = car2_name
        existing.car1_name = car1_name
        existing.match_score = match_score
        existing.source = "sync"
        return 0, 0
    db.session.add(
        VehicleCodeMapping(
            level=level,
            car2_code=car2_code,
            car1_code=car1_code,
            car2_name=car2_name,
            car1_name=car1_name,
            status="candidate",
            match_score=match_score,
            source="sync",
        )
    )
    return 1, 0


def _sync_level_items(
    level: str,
    items: list[dict],
    *,
    model: type,
    pk_attr: str,
    name_attr: str,
    parent_attr: str | None,
    parent_car1_code: str | None,
) -> tuple[int, int]:
    created = skipped = 0
    for item in items:
        car2_code = _clean(str(item.get(pk_attr) or ""))
        car2_name = _clean(item.get(name_attr))
        if not car2_code:
            continue
        car1_code, car1_name, score = _match_car1_name(
            level,
            car2_name,
            model=model,
            pk_attr=pk_attr,
            name_attr=name_attr,
            parent_attr=parent_attr,
            parent_code=parent_car1_code,
        )
        if not car1_code:
            continue
        c, s = _upsert_candidate(
            level, car2_code, car1_code, car2_name, car1_name, score
        )
        created += c
        skipped += s
    return created, skipped


def sync_candidates_from_car2(base_url: str | None = None) -> dict[str, Any]:
    base = base_url or current_app.config["CAR2_CODES_BASE_URL"]
    created = skipped = 0
    try:
        makers = _fetch_items(base, "/api/codes/makers")
        for maker_item in makers:
            car2_maker_no = _clean(str(maker_item.get("maker_no") or ""))
            car2_maker_name = _clean(maker_item.get("maker_name"))
            if not car2_maker_no:
                continue
            car1_maker_no, car1_maker_name, score = _match_car1_name(
                "maker",
                car2_maker_name,
                model=VehicleMaker,
                pk_attr="maker_no",
                name_attr="maker_name",
                parent_attr=None,
                parent_code=None,
            )
            if car1_maker_no:
                c, s = _upsert_candidate(
                    "maker",
                    car2_maker_no,
                    car1_maker_no,
                    car2_maker_name,
                    car1_maker_name,
                    score,
                )
                created += c
                skipped += s
            else:
                continue

            models = _fetch_items(
                base, "/api/codes/models", {"maker_no": car2_maker_no}
            )
            c, s = _sync_level_items(
                "model",
                models,
                model=VehicleModel,
                pk_attr="model_no",
                name_attr="model_name",
                parent_attr="maker_no",
                parent_car1_code=car1_maker_no,
            )
            created += c
            skipped += s

            for model_item in models:
                car2_model_no = _clean(str(model_item.get("model_no") or ""))
                if not car2_model_no:
                    continue
                car1_model_no, _, _ = _match_car1_name(
                    "model",
                    _clean(model_item.get("model_name")),
                    model=VehicleModel,
                    pk_attr="model_no",
                    name_attr="model_name",
                    parent_attr="maker_no",
                    parent_code=car1_maker_no,
                )
                if not car1_model_no:
                    continue

                mdetails = _fetch_items(
                    base,
                    "/api/codes/modeldetails",
                    {"model_no": car2_model_no},
                )
                c, s = _sync_level_items(
                    "mdetail",
                    mdetails,
                    model=VehicleModelDetail,
                    pk_attr="mdetail_no",
                    name_attr="mdetail_name",
                    parent_attr="model_no",
                    parent_car1_code=car1_model_no,
                )
                created += c
                skipped += s

                for mdetail_item in mdetails:
                    car2_mdetail_no = _clean(str(mdetail_item.get("mdetail_no") or ""))
                    if not car2_mdetail_no:
                        continue
                    car1_mdetail_no, _, _ = _match_car1_name(
                        "mdetail",
                        _clean(mdetail_item.get("mdetail_name")),
                        model=VehicleModelDetail,
                        pk_attr="mdetail_no",
                        name_attr="mdetail_name",
                        parent_attr="model_no",
                        parent_code=car1_model_no,
                    )
                    if not car1_mdetail_no:
                        continue

                    grades = _fetch_items(
                        base,
                        "/api/codes/grades",
                        {"mdetail_no": car2_mdetail_no},
                    )
                    c, s = _sync_level_items(
                        "grade",
                        grades,
                        model=VehicleGrade,
                        pk_attr="grade_no",
                        name_attr="grade_name",
                        parent_attr="mdetail_no",
                        parent_car1_code=car1_mdetail_no,
                    )
                    created += c
                    skipped += s

                    for grade_item in grades:
                        car2_grade_no = _clean(str(grade_item.get("grade_no") or ""))
                        if not car2_grade_no:
                            continue
                        car1_grade_no, _, _ = _match_car1_name(
                            "grade",
                            _clean(grade_item.get("grade_name")),
                            model=VehicleGrade,
                            pk_attr="grade_no",
                            name_attr="grade_name",
                            parent_attr="mdetail_no",
                            parent_code=car1_mdetail_no,
                        )
                        if not car1_grade_no:
                            continue

                        gdetails = _fetch_items(
                            base,
                            "/api/codes/gradedetails",
                            {"grade_no": car2_grade_no},
                        )
                        c, s = _sync_level_items(
                            "gdetail",
                            gdetails,
                            model=VehicleGradeDetail,
                            pk_attr="gdetail_no",
                            name_attr="gdetail_name",
                            parent_attr="grade_no",
                            parent_car1_code=car1_grade_no,
                        )
                        created += c
                        skipped += s

        db.session.commit()
        return {"ok": True, "created": created, "skipped": skipped, "error": None}
    except Exception as exc:
        db.session.rollback()
        return {"ok": False, "created": created, "skipped": skipped, "error": str(exc)}


def import_csv(text: str, *, force: bool = False) -> dict[str, Any]:
    created = updated = skipped = 0
    try:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or set(_CSV_HEADER) - set(reader.fieldnames):
            return {
                "ok": False,
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "error": "invalid CSV header",
            }
        for row in reader:
            level = _clean(row.get("level"))
            car2_code = _clean(row.get("car2_code"))
            car1_code = _clean(row.get("car1_code"))
            if not level or not car2_code or not car1_code:
                continue
            existing = _get_mapping(level, car2_code)
            if existing:
                if existing.status in _PROTECTED and not force:
                    skipped += 1
                    continue
                if _confirmed_car1_conflict(level, car1_code, exclude_car2=car2_code):
                    skipped += 1
                    continue
                existing.car1_code = car1_code
                existing.car2_name = _clean(row.get("car2_name"))
                existing.car1_name = _clean(row.get("car1_name"))
                existing.status = "confirmed"
                existing.source = "csv"
                updated += 1
            else:
                if _confirmed_car1_conflict(level, car1_code):
                    skipped += 1
                    continue
                db.session.add(
                    VehicleCodeMapping(
                        level=level,
                        car2_code=car2_code,
                        car1_code=car1_code,
                        car2_name=_clean(row.get("car2_name")),
                        car1_name=_clean(row.get("car1_name")),
                        status="confirmed",
                        source="csv",
                    )
                )
                created += 1
        db.session.commit()
        return {
            "ok": True,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "error": None,
        }
    except Exception as exc:
        db.session.rollback()
        return {
            "ok": False,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "error": str(exc),
        }


def export_csv() -> str:
    rows = db.session.execute(
        db.select(VehicleCodeMapping).order_by(
            VehicleCodeMapping.level, VehicleCodeMapping.car2_code
        )
    ).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_HEADER)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "level": row.level,
                "car2_code": row.car2_code,
                "car1_code": row.car1_code,
                "car2_name": row.car2_name or "",
                "car1_name": row.car1_name or "",
            }
        )
    return buf.getvalue()


def set_mapping_status(mapping_id: int, status: str) -> bool:
    if status not in _STATUSES:
        return False
    row = db.session.get(VehicleCodeMapping, mapping_id)
    if not row:
        return False
    if status == "confirmed" and _confirmed_car1_conflict(
        row.level, row.car1_code, exclude_car2=row.car2_code
    ):
        return False
    row.status = status
    db.session.commit()
    return True
