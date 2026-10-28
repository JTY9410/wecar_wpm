"""위카 차량정보 조회 API — 관리자 설정 키로 form POST."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import requests

from app.extensions import db
from app.models import CarInfoCache, LLMConfig
from config import Config

logger = logging.getLogger(__name__)

DEFAULT_URL = "https://diag.wecarmobility.co.kr/api/get_car_info"
_PROVIDER = "wecar_car_info"
_TIMEOUT = 15


def normalize_car_no(car_no: str | None) -> str:
    return re.sub(r"\s+", "", (car_no or "").strip())


def _row() -> LLMConfig | None:
    return db.session.execute(
        db.select(LLMConfig).where(LLMConfig.provider == _PROVIDER)
    ).scalar_one_or_none()


def resolve_authkey() -> str:
    row = _row()
    if row and row.api_key:
        return row.api_key.strip()
    return (getattr(Config, "WECAR_CAR_INFO_AUTHKEY", "") or "").strip()


def resolve_api_url() -> str:
    row = _row()
    if row and row.model_name and str(row.model_name).strip():
        return str(row.model_name).strip()
    return (getattr(Config, "WECAR_CAR_INFO_URL", "") or DEFAULT_URL).strip() or DEFAULT_URL


def is_configured() -> bool:
    return bool(resolve_authkey())


def key_hint() -> str:
    key = resolve_authkey()
    if len(key) >= 12:
        return f"{key[:4]}...{key[-4:]}"
    return "설정됨" if key else "미설정"


def save_settings(*, api_key=None, api_url=None, clear_key=False):
    row = _row()
    if row is None:
        row = LLMConfig(provider=_PROVIDER, is_active=False)
        db.session.add(row)
    if clear_key:
        row.api_key = None
    elif api_key is not None and str(api_key).strip():
        row.api_key = str(api_key).strip()
    if api_url is not None:
        text = str(api_url).strip()
        row.model_name = text or DEFAULT_URL
    db.session.commit()
    return row


def _parse_optional_number(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value


def normalize_dto(dto: dict) -> dict:
    out = dict(dto or {})
    for key in ("diag_displacement", "diag_capacity", "diag_payload", "diag_new_price"):
        out[key] = _parse_optional_number(out.get(key))
    price = out.get("diag_new_price")
    if isinstance(price, (int, float)) and price > 0:
        out["diag_new_price_manwon"] = int(round(price / 10000))
    else:
        out["diag_new_price_manwon"] = None
    return out


def fetch_car_info(car_no: str, *, use_cache: bool = True, force: bool = False) -> dict:
    plate = normalize_car_no(car_no)
    if not plate:
        return {"ok": False, "error": "차량번호가 누락되었습니다.", "car_no": plate}

    if use_cache and not force:
        cached = db.session.get(CarInfoCache, plate)
        if cached and cached.payload_json:
            try:
                dto = normalize_dto(json.loads(cached.payload_json))
                return {
                    "ok": True,
                    "car_no": plate,
                    "dto": dto,
                    "cached": True,
                    "fetched_at": cached.fetched_at.isoformat() if cached.fetched_at else None,
                }
            except json.JSONDecodeError:
                pass

    if not is_configured():
        return {
            "ok": False,
            "error": "위카 차량정보 API 인증키가 설정되지 않았습니다.",
            "car_no": plate,
        }

    try:
        resp = requests.post(
            resolve_api_url(),
            data={"authkey": resolve_authkey(), "car_no": plate},
            timeout=_TIMEOUT,
        )
        body = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("car info API failed: %s", exc)
        return {"ok": False, "error": str(exc), "car_no": plate}

    if body.get("status") != "ok":
        return {
            "ok": False,
            "error": body.get("msg") or "조회 실패",
            "car_no": plate,
            "msg": body.get("msg"),
        }

    dto = normalize_dto(body.get("dto") or {})
    now = datetime.now(timezone.utc)
    payload = json.dumps(dto, ensure_ascii=False)
    row = db.session.get(CarInfoCache, plate)
    if row:
        row.payload_json = payload
        row.fetched_at = now
        row.source = dto.get("diag_info_api") or "autoup"
    else:
        db.session.add(CarInfoCache(
            car_no=plate,
            payload_json=payload,
            source=dto.get("diag_info_api") or "autoup",
            fetched_at=now,
        ))
    db.session.commit()
    return {
        "ok": True,
        "car_no": plate,
        "dto": dto,
        "cached": False,
        "fetched_at": now.isoformat(),
        "msg": body.get("msg"),
    }


def test_connection() -> dict:
    if not is_configured():
        return {"ok": False, "error": "API 인증키가 설정되지 않았습니다."}
    try:
        resp = requests.post(
            resolve_api_url(),
            data={"authkey": resolve_authkey(), "car_no": ""},
            timeout=_TIMEOUT,
        )
        body = resp.json()
    except requests.Timeout:
        return {"ok": False, "error": "API 응답 시간 초과. 네트워크를 확인해 주세요."}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"연결 실패: {exc}"}

    msg = (body.get("msg") or "").strip()
    if "인증" in msg and ("키" in msg or "실패" in msg or "오류" in msg):
        return {"ok": False, "error": f"인증 실패: {msg}"}
    if body.get("status") == "ok":
        return {"ok": True, "detail": "API 응답 정상"}
    if "차량번호" in msg or "누락" in msg:
        return {"ok": True, "detail": f"인증 확인됨 ({msg})"}
    if body.get("status") == "fail" and "인증" not in msg:
        return {"ok": True, "detail": f"인증 확인됨 ({msg})"}
    return {"ok": False, "error": msg or "연결 실패"}
