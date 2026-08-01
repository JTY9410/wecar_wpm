"""로컬 이미지 보안 캐싱 (PRD §5.5). 외부 URL은 프론트에 직접 노출 금지."""
import os
import re

import requests

from config import Config

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def _safe_car_no(car_no):
    """외부 API가 내려주는 car_no를 파일명으로 쓰기 전에 경로 조작 문자를 제거."""
    return _UNSAFE_CHARS.sub("_", str(car_no))


def cache_image(car_no, image_url, session=None):
    """Download external image to local safe storage. Returns virtual URL or None."""
    if not image_url:
        return None
    session = session or requests
    safe_no = _safe_car_no(car_no)
    dest = os.path.join(Config.IMAGE_STORAGE_PATH, f"{safe_no}_main.jpg")
    os.makedirs(Config.IMAGE_STORAGE_PATH, exist_ok=True)
    try:
        resp = session.get(image_url, timeout=Config.API_TIMEOUT)
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            fh.write(resp.content)
        return f"{Config.IMAGE_URL_PREFIX}/{safe_no}_main.jpg"
    except Exception:
        return None  # graceful: sync continues, placeholder used


def local_url(car_no):
    safe_no = _safe_car_no(car_no)
    dest = os.path.join(Config.IMAGE_STORAGE_PATH, f"{safe_no}_main.jpg")
    if os.path.exists(dest):
        return f"{Config.IMAGE_URL_PREFIX}/{safe_no}_main.jpg"
    return None
