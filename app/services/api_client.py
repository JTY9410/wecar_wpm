"""KS API client with fallback — page/stream friendly (no full in-memory list)."""
import json
import logging
import tempfile
from collections.abc import Iterator
from pathlib import Path

import requests

from config import Config

logger = logging.getLogger(__name__)


class ApiUnavailable(Exception):
    pass


def _parse_list(data) -> list | None:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "items", "result", "List"):
            if key in data and isinstance(data[key], list):
                return data[key]
        if "CarNo" in data or "car_no" in data:
            return [data]
    return None


def _download_to_temp(url: str, session, timeout: int, params: dict | None = None) -> Path:
    """Stream HTTP body to a temp file (avoids holding the full bytes+JSON twice)."""
    resp = session.get(url, params=params, timeout=timeout, stream=True)
    resp.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(prefix="listings_", suffix=".json", delete=False)
    try:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            if chunk:
                tmp.write(chunk)
        tmp.flush()
        return Path(tmp.name)
    finally:
        tmp.close()
        resp.close()


def _iter_json_array_batches(path: Path, batch_size: int) -> Iterator[list[dict]]:
    """Yield batches from a JSON file: either a top-level array or {data:[...]}."""
    try:
        import ijson
    except ImportError:
        ijson = None

    if ijson is not None:
        for prefix in ("data.item", "items.item", "result.item", "List.item", "item"):
            batch: list[dict] = []
            try:
                with path.open("rb") as fh:
                    for obj in ijson.items(fh, prefix):
                        if isinstance(obj, dict):
                            batch.append(obj)
                            if len(batch) >= batch_size:
                                yield batch
                                batch = []
                if batch:
                    yield batch
                return
            except Exception:
                continue

    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    items = _parse_list(data) or []
    del data
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]
    del items


def iter_listing_pages(
    per_page: int | None = None,
    session=None,
) -> Iterator[tuple[list[dict], str]]:
    """
    Yield listing pages without accumulating the full feed in one list.

    Always streams the HTTP body to disk first, then yields fixed-size batches
    (ijson when available). Server pagination is used when page 1 has exactly
    ``per_page`` items.
    """
    size = per_page or getattr(Config, "SYNC_BATCH_SIZE", 500)
    session = session or requests
    bases = [
        (Config.KS_API_BASE_URL, "primary"),
        (Config.FALLBACK_API_BASE_URL, "fallback"),
    ]
    last_error = None

    for base_url, source in bases:
        if not base_url:
            continue
        listings_url = f"{base_url.rstrip('/')}/{Config.LISTINGS_PATH.lstrip('/')}"
        try:
            page = 1
            while True:
                path = _download_to_temp(
                    listings_url,
                    session,
                    Config.API_TIMEOUT,
                    params={"page": page, "limit": size},
                )
                try:
                    page_total = 0
                    for batch in _iter_json_array_batches(path, size):
                        if not batch:
                            continue
                        page_total += len(batch)
                        yield batch, source
                finally:
                    path.unlink(missing_ok=True)

                if page_total == 0:
                    if page == 1:
                        return
                    break
                # API ignored limit → full dump on this "page"
                if page_total > size:
                    return
                if page_total < size:
                    return
                page += 1
            return
        except Exception as exc:
            last_error = exc
            logger.warning("listings fetch failed from %s: %s", base_url, exc)

    raise ApiUnavailable(str(last_error) if last_error else "no API base configured")


def fetch_listings(session=None):
    """Backward-compatible helper — prefer iter_listing_pages for new code."""
    items: list[dict] = []
    source = "none"
    for batch, src in iter_listing_pages(session=session):
        source = src
        items.extend(batch)
    return {"data": items}, source
