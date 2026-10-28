"""오토업 car-info dto → 도매시세(MarketSummary) 트림 매핑."""
from __future__ import annotations

import re

from sqlalchemy import distinct, select

from app.extensions import db
from app.models import DiagTrimMapping, MarketSummary
from app.services import market_query

_MAKER_ALIASES = {
    "쌍용": "KG모빌리티(쌍용)",
    "KG모빌리티": "KG모빌리티(쌍용)",
    "KG 모빌리티": "KG모빌리티(쌍용)",
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

_FUEL_ALIASES = {
    "휘발유": "가솔린",
    "가솔린": "가솔린",
    "경유": "디젤",
    "디젤": "디젤",
    "LPG": "LPG",
    "lpg": "LPG",
    "전기": "전기",
    "하이브리드": "하이브리드",
    "가솔린+전기": "하이브리드",
    "휘발유+전기": "하이브리드",
}

_LEVELS = ("maker", "model", "mdetail", "grade", "gdetail")


def _clean(value: str | None) -> str:
    text = (value or "").strip()
    return "" if text.lower() in {"", "null", "none", "없음", "-"} else text


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", _clean(text))


def _canon(text: str | None) -> str:
    s = _norm(text).lower()
    s = re.sub(r"[^0-9a-z가-힣.]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _strip_paren(text: str) -> str:
    return _norm(re.sub(r"\s*\([^)]*\)\s*", " ", text or ""))


def _tokens(text: str | None) -> set[str]:
    return {t for t in _canon(text).split() if t and t not in {"형", "용", "인승"}}


def _idx(dto: dict, key: str) -> str:
    val = dto.get(key)
    if val in (None, ""):
        return ""
    return str(val).strip()


def _score(candidate: str, targets: list[str]) -> float:
    cand = _tokens(candidate) | _tokens(_strip_paren(candidate))
    if not cand:
        return 0.0
    want: set[str] = set()
    for t in targets:
        want |= _tokens(t)
        want |= _tokens(_strip_paren(t))
    if not want:
        return 0.0
    inter = cand & want
    if not inter:
        return 0.0
    return (len(inter) / len(want)) * 0.65 + (len(inter) / len(cand)) * 0.35


def get_mapped(level: str, diag_idx: str) -> DiagTrimMapping | None:
    if not diag_idx:
        return None
    return db.session.execute(
        select(DiagTrimMapping).where(
            DiagTrimMapping.level == level,
            DiagTrimMapping.diag_idx == diag_idx,
            DiagTrimMapping.status == "confirmed",
        )
    ).scalar_one_or_none()


def save_mapping(
    *,
    level: str,
    diag_idx: str,
    market_name: str,
    diag_name: str | None = None,
    status: str = "confirmed",
    match_score: float | None = None,
    source: str = "auto",
    parent_market_name: str | None = None,
) -> DiagTrimMapping | None:
    if not level or not diag_idx or not market_name:
        return None
    row = db.session.execute(
        select(DiagTrimMapping).where(
            DiagTrimMapping.level == level,
            DiagTrimMapping.diag_idx == diag_idx,
        )
    ).scalar_one_or_none()
    if row is None:
        row = DiagTrimMapping(level=level, diag_idx=diag_idx)
        db.session.add(row)
    elif row.status == "rejected" and source == "auto":
        return row
    row.diag_name = diag_name
    row.market_name = market_name
    row.status = status
    row.match_score = match_score
    row.source = source
    row.parent_market_name = parent_market_name
    db.session.commit()
    return row


def _candidates(
    level: str,
    *,
    maker: str | None = None,
    model_name: str | None = None,
    mdetail_name: str | None = None,
    grade_name: str | None = None,
) -> list[str]:
    col = {
        "maker": MarketSummary.maker,
        "model": MarketSummary.model_name,
        "mdetail": MarketSummary.mdetail_name,
        "grade": MarketSummary.grade_name,
        "gdetail": MarketSummary.gdetail_name,
        "fuel": MarketSummary.fuel,
    }[level]
    stmt = select(distinct(col)).where(col.isnot(None), col != "")
    if maker and level != "maker":
        stmt = stmt.where(MarketSummary.maker == maker)
    if model_name and level in ("mdetail", "grade", "gdetail"):
        stmt = stmt.where(MarketSummary.model_name == model_name)
    if mdetail_name and level in ("grade", "gdetail"):
        stmt = stmt.where(MarketSummary.mdetail_name == mdetail_name)
    if grade_name and level == "gdetail":
        stmt = stmt.where(MarketSummary.grade_name == grade_name)
    rows = db.session.execute(stmt.limit(2000)).scalars().all()
    return [r for r in rows if _clean(r)]


def _match_name(candidates: list[str], *targets: str) -> tuple[str | None, str, float | None]:
    wants = [_norm(t) for t in targets if _norm(t)]
    if not wants or not candidates:
        return None, "none", None

    for t in wants:
        aliases = [_MAKER_ALIASES.get(t, t), t]
        exact = [c for c in candidates if _norm(c) in aliases or _canon(c) == _canon(t)]
        if len(exact) == 1:
            return exact[0], "exact", 1.0
        if len(exact) > 1:
            # prefer alias hit
            for a in aliases:
                hit = [c for c in exact if _norm(c) == _norm(a)]
                if len(hit) == 1:
                    return hit[0], "exact", 1.0
            return None, "ambiguous", None
        st = _strip_paren(t)
        if st and st != t:
            exact2 = [c for c in candidates if _strip_paren(c) == st or _canon(c) == _canon(st)]
            if len(exact2) == 1:
                return exact2[0], "exact", 0.95

    scored = []
    for c in candidates:
        sc = _score(c, wants)
        if sc >= 0.45:
            scored.append((sc, c))
    if not scored:
        return None, "none", None
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.08:
        return None, "ambiguous", scored[0][0]
    return scored[0][1], "partial", scored[0][0]


def _resolve_level(
    level: str,
    dto: dict,
    idx_key: str,
    name_key: str,
    *,
    parent_market_name: str | None = None,
    extra_targets: list[str] | None = None,
    scope: dict | None = None,
) -> tuple[str | None, str]:
    diag_idx = _idx(dto, idx_key)
    diag_name = _clean(dto.get(name_key))
    mapped = get_mapped(level, diag_idx)
    if mapped:
        return mapped.market_name, "mapped"

    scope = scope or {}
    cands = _candidates(level, **scope)
    targets = [diag_name, *(extra_targets or [])]
    if level == "maker" and diag_name:
        targets = [_MAKER_ALIASES.get(diag_name, diag_name), diag_name]
    name, how, score = _match_name(cands, *targets)
    if name and how in ("exact", "partial") and diag_idx:
        save_mapping(
            level=level,
            diag_idx=diag_idx,
            market_name=name,
            diag_name=diag_name,
            status="confirmed",
            match_score=score,
            source="auto",
            parent_market_name=parent_market_name,
        )
    return name, how


def map_fuel(diag_fuel: str | None) -> str | None:
    raw = _clean(diag_fuel)
    if not raw:
        return None
    alias = _FUEL_ALIASES.get(raw) or _FUEL_ALIASES.get(raw.upper()) or raw
    cands = _candidates("fuel")
    if alias in cands:
        return alias
    name, how, _ = _match_name(cands, alias, raw)
    return name if how != "ambiguous" else alias


def resolve_market_filters(dto: dict | None) -> dict:
    """dto → market_query.grid 필터 + 매칭 메타."""
    dto = dto or {}
    notes = []
    maker, how = _resolve_level("maker", dto, "diag_company_idx", "diag_company")
    if not maker:
        notes.append("제조사 미매칭" if how != "ambiguous" else "제조사 매칭 모호")

    model = None
    if maker:
        model, how = _resolve_level(
            "model", dto, "diag_model_idx", "diag_model",
            parent_market_name=maker,
            scope={"maker": maker},
        )
        if not model:
            notes.append("모델 미매칭" if how != "ambiguous" else "모델 매칭 모호")

    mdetail = None
    if maker and model:
        mdetail, how = _resolve_level(
            "mdetail", dto, "diag_submodel_idx", "diag_submodel",
            parent_market_name=model,
            extra_targets=[_clean(dto.get("diag_model"))],
            scope={"maker": maker, "model_name": model},
        )
        if not mdetail and how == "none":
            notes.append("세부모델 미매칭(상위 모델로 조회)")

    grade = None
    if maker and model:
        grade, how = _resolve_level(
            "grade", dto, "diag_grade_idx", "diag_grade",
            parent_market_name=mdetail or model,
            scope={"maker": maker, "model_name": model, "mdetail_name": mdetail},
        )
        if not grade and how != "exact":
            notes.append("등급 미매칭" if how == "none" else "등급 매칭 모호")

    gdetail = None
    if maker and model and grade:
        gdetail, how = _resolve_level(
            "gdetail", dto, "diag_subgrade_idx", "diag_subgrade",
            parent_market_name=grade,
            scope={
                "maker": maker,
                "model_name": model,
                "mdetail_name": mdetail,
                "grade_name": grade,
            },
        )

    fuel = map_fuel(dto.get("diag_fuel"))
    year = dto.get("diag_year")
    try:
        year = int(year) if year not in (None, "") else None
    except (TypeError, ValueError):
        year = None

    filters = {
        "maker": maker,
        "model_name": model,
        "mdetail_name": mdetail,
        "grade_name": grade,
        "gdetail_name": gdetail,
        "car_year": year,
        "fuel": fuel,
    }
    path = " / ".join(
        x for x in (maker, model, mdetail, grade, gdetail) if x
    )
    return {
        "ok": bool(maker),
        "filters": filters,
        "path": path,
        "notes": notes,
        "diag": {
            "company": _clean(dto.get("diag_company")),
            "model": _clean(dto.get("diag_model")),
            "submodel": _clean(dto.get("diag_submodel")),
            "grade": _clean(dto.get("diag_grade")),
            "subgrade": _clean(dto.get("diag_subgrade")),
            "year": year,
            "fuel": _clean(dto.get("diag_fuel")),
            "color": _clean(dto.get("diag_color")),
            "vin": _clean(dto.get("diag_car_id")),
            "new_price_manwon": dto.get("diag_new_price_manwon"),
            "registered_date": _clean(dto.get("diag_registred_date")),
            "distance_standard": dto.get("diag_distance_standard"),
        },
    }


def lookup_plate_market(car_no: str, *, lang: str = "ko") -> dict:
    from app.services import car_info_api

    info = car_info_api.fetch_car_info(car_no)
    if not info.get("ok"):
        return {
            "ok": False,
            "error": info.get("error") or "조회 실패",
            "car_no": info.get("car_no") or car_no,
            "car_info_configured": car_info_api.is_configured(),
        }

    resolved = resolve_market_filters(info.get("dto"))
    rows = []
    if resolved.get("ok"):
        f = resolved["filters"]
        rows = market_query.grid(
            maker=f.get("maker"),
            model_name=f.get("model_name"),
            mdetail_name=f.get("mdetail_name"),
            grade_name=f.get("grade_name"),
            gdetail_name=f.get("gdetail_name"),
            car_year=f.get("car_year"),
            fuel=f.get("fuel"),
            lang=lang,
        )
        # 세부등급까지 맞췄는데 표본 없으면 등급 단위로 완화
        if not rows and f.get("gdetail_name"):
            rows = market_query.grid(
                maker=f.get("maker"),
                model_name=f.get("model_name"),
                mdetail_name=f.get("mdetail_name"),
                grade_name=f.get("grade_name"),
                car_year=f.get("car_year"),
                fuel=f.get("fuel"),
                lang=lang,
            )
            if rows:
                resolved["notes"].append("세부등급 시세 없음 → 등급 단위로 완화")
        if not rows and f.get("grade_name"):
            rows = market_query.grid(
                maker=f.get("maker"),
                model_name=f.get("model_name"),
                mdetail_name=f.get("mdetail_name"),
                car_year=f.get("car_year"),
                fuel=f.get("fuel"),
                lang=lang,
            )
            if rows:
                resolved["notes"].append("등급 시세 없음 → 세부모델/모델 단위로 완화")

    return {
        "ok": True,
        "car_no": info["car_no"],
        "cached": info.get("cached"),
        "fetched_at": info.get("fetched_at"),
        "dto": info.get("dto"),
        "mapping": resolved,
        "rows": rows,
        "count": len(rows),
        "car_info_configured": True,
    }


def set_mapping_status(mapping_id: int, status: str) -> bool:
    if status not in ("candidate", "confirmed", "rejected"):
        return False
    row = db.session.get(DiagTrimMapping, mapping_id)
    if not row:
        return False
    row.status = status
    db.session.commit()
    return True


def list_mappings(status: str = "", level: str = "", limit: int = 200) -> list[DiagTrimMapping]:
    q = select(DiagTrimMapping).order_by(DiagTrimMapping.updated_at.desc())
    if status in ("candidate", "confirmed", "rejected"):
        q = q.where(DiagTrimMapping.status == status)
    if level in _LEVELS or level == "fuel":
        q = q.where(DiagTrimMapping.level == level)
    return list(db.session.execute(q.limit(limit)).scalars().all())
