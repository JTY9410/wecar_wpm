"""로컬 이미지 보안 캐싱 (PRD §5.5). 외부 URL은 프론트에 직접 노출 금지."""
import os

import requests

from config import Config


def cache_image(car_no, image_url, session=None):
    """Download external image to local safe storage. Returns virtual URL or None."""
    if not image_url:
        return None
    session = session or requests
    dest = os.path.join(Config.IMAGE_STORAGE_PATH, f"{car_no}_main.jpg")
    os.makedirs(Config.IMAGE_STORAGE_PATH, exist_ok=True)
    try:
        resp = session.get(image_url, timeout=Config.API_TIMEOUT)
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            fh.write(resp.content)
        return f"{Config.IMAGE_URL_PREFIX}/{car_no}_main.jpg"
    except Exception:
        return None  # graceful: sync continues, placeholder used


def local_url(car_no):
    dest = os.path.join(Config.IMAGE_STORAGE_PATH, f"{car_no}_main.jpg")
    if os.path.exists(dest):
        return f"{Config.IMAGE_URL_PREFIX}/{car_no}_main.jpg"
    return None
