"""KS API client with fallback endpoint (PRD §5.4)."""
import requests

from config import Config


class ApiUnavailable(Exception):
    pass


def fetch_listings(session=None):
    """Try primary KS API, fall back to backup endpoint on any failure.
    Returns (data, source) where source is 'primary' or 'fallback'."""
    session = session or requests
    primary = f"{Config.KS_API_BASE_URL.rstrip('/')}/{Config.LISTINGS_PATH}"
    fallback = f"{Config.FALLBACK_API_BASE_URL.rstrip('/')}/{Config.LISTINGS_PATH}"
    try:
        resp = session.get(primary, timeout=Config.API_TIMEOUT)
        resp.raise_for_status()
        return resp.json(), "primary"
    except Exception:
        try:
            resp = session.get(fallback, timeout=Config.API_TIMEOUT)
            resp.raise_for_status()
            return resp.json(), "fallback"
        except Exception as exc:
            raise ApiUnavailable(str(exc))
