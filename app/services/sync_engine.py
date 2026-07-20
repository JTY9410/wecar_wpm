"""실시간 매물 동기화 — 청크 스트리밍 + 배치 커밋 (저메모리)."""
import logging
import tempfile
from pathlib import Path

from sqlalchemy import text

from app.extensions import db
from app.models import Listing, SyncLog
from app.services.api_client import ApiUnavailable, iter_listing_pages
from app.services.image_cache import cache_image
from config import Config

logger = logging.getLogger(__name__)


def _extract_image_url(item):
    info = item.get("ImageInfo")
    if isinstance(info, list) and info:
        return info[0].get("ImageUrl")
    return item.get("ImageUrl")


def _to_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _to_str_code(val):
    if val in (None, "", "0", 0):
        return None
    return str(val)


def _upsert_listing(item: dict, with_images: bool) -> str | None:
    car_no = str(item.get("CarNo") or item.get("car_no") or "").strip()
    if not car_no:
        return None
    listing = db.session.get(Listing, car_no) or Listing(car_no=car_no)
    listing.car_name = item.get("CarName") or item.get("car_name")
    listing.maker_no = _to_str_code(item.get("MakerNo") or item.get("maker_no"))
    listing.model_no = _to_str_code(item.get("ModelNo") or item.get("model_no"))
    listing.mdetail_no = _to_str_code(item.get("MDetailNo") or item.get("mdetail_no"))
    listing.grade_no = _to_str_code(item.get("GradeNo") or item.get("grade_no"))
    listing.gdetail_no = _to_str_code(item.get("GdetailNo") or item.get("gdetail_no"))
    listing.car_year = _to_int(item.get("CarYear") or item.get("car_year"))
    listing.car_km = _to_int(item.get("CarKm") or item.get("car_km"))
    listing.car_amount_sale = _to_int(item.get("CarAmountSale") or item.get("car_amount_sale"))
    listing.sido = item.get("Sido") or item.get("sido")
    listing.kind_name = item.get("KindName") or item.get("kind_name")
    listing.imported = item.get("Imported") or item.get("imported")
    listing.car_fuel = item.get("CarFuel") or item.get("car_fuel")
    listing.is_sold = False
    if with_images:
        url = cache_image(car_no, _extract_image_url(item))
        if url:
            listing.image_url = url
    db.session.add(listing)
    return car_no


def _mark_sold_via_seen_file(seen_path: Path) -> int:
    """Mark listings not present in seen_path as sold — no giant in-memory set."""
    bind = db.session.get_bind()
    dialect = bind.dialect.name if bind is not None else "sqlite"

    if dialect == "sqlite":
        db.session.execute(text("CREATE TEMP TABLE IF NOT EXISTS sync_seen (car_no TEXT PRIMARY KEY)"))
        db.session.execute(text("DELETE FROM sync_seen"))
        with seen_path.open("r", encoding="utf-8") as fh:
            chunk: list[dict] = []
            for line in fh:
                car_no = line.strip()
                if not car_no:
                    continue
                chunk.append({"car_no": car_no})
                if len(chunk) >= 1000:
                    db.session.execute(
                        text("INSERT OR IGNORE INTO sync_seen (car_no) VALUES (:car_no)"),
                        chunk,
                    )
                    chunk = []
            if chunk:
                db.session.execute(
                    text("INSERT OR IGNORE INTO sync_seen (car_no) VALUES (:car_no)"),
                    chunk,
                )
        result = db.session.execute(text(
            "UPDATE listing SET is_sold = 1 "
            "WHERE is_sold = 0 AND car_no NOT IN (SELECT car_no FROM sync_seen)"
        ))
        db.session.execute(text(
            "UPDATE listing SET is_sold = 0 "
            "WHERE car_no IN (SELECT car_no FROM sync_seen)"
        ))
        db.session.execute(text("DROP TABLE IF EXISTS sync_seen"))
        return int(result.rowcount or 0)

    # Generic fallback (PostgreSQL etc.): batch updates from file
    db.session.execute(text(
        "CREATE TEMP TABLE IF NOT EXISTS sync_seen (car_no VARCHAR(50) PRIMARY KEY)"
    ))
    db.session.execute(text("DELETE FROM sync_seen"))
    with seen_path.open("r", encoding="utf-8") as fh:
        chunk = []
        for line in fh:
            car_no = line.strip()
            if not car_no:
                continue
            chunk.append({"car_no": car_no})
            if len(chunk) >= 1000:
                db.session.execute(
                    text("INSERT INTO sync_seen (car_no) VALUES (:car_no) ON CONFLICT DO NOTHING"),
                    chunk,
                )
                chunk = []
        if chunk:
            db.session.execute(
                text("INSERT INTO sync_seen (car_no) VALUES (:car_no) ON CONFLICT DO NOTHING"),
                chunk,
            )
    result = db.session.execute(text(
        "UPDATE listing SET is_sold = true "
        "WHERE is_sold = false AND car_no NOT IN (SELECT car_no FROM sync_seen)"
    ))
    db.session.execute(text(
        "UPDATE listing SET is_sold = false "
        "WHERE car_no IN (SELECT car_no FROM sync_seen)"
    ))
    return int(result.rowcount or 0)


def sync_listings(fetch=None, fetch_pages=None, with_images=True, batch_size=None):
    """
    Chunked sync. Does not build one giant listings list.

    fetch: legacy test hook returning ({"data": [...]}, source).
    fetch_pages: callable yielding (batch, source) tuples.
    """
    size = batch_size or getattr(Config, "SYNC_BATCH_SIZE", 500)

    def _page_iter():
        if fetch is not None:
            data, src = fetch()
            items = data.get("data", []) if isinstance(data, dict) else (data or [])
            for i in range(0, len(items), size):
                yield items[i : i + size], src
            return
        if fetch_pages is not None:
            yield from fetch_pages()
            return
        yield from iter_listing_pages(per_page=size)

    seen_path = Path(tempfile.mkstemp(prefix="sync_seen_", suffix=".txt")[1])
    processed = 0
    source = "none"

    try:
        try:
            for batch, src in _page_iter():
                source = src
                with seen_path.open("a", encoding="utf-8") as seen_fh:
                    for item in batch:
                        car_no = _upsert_listing(item, with_images=with_images)
                        if car_no:
                            seen_fh.write(car_no + "\n")
                            processed += 1
                db.session.commit()
                db.session.expunge_all()
                batch.clear()
        except ApiUnavailable as exc:
            log = SyncLog(
                sync_type="AUTO_API_SYNC", status="FAIL",
                records_processed=0, error_message=str(exc),
            )
            db.session.add(log)
            db.session.commit()
            return {"status": "FAIL", "error": str(exc)}

        sold = _mark_sold_via_seen_file(seen_path)
        log = SyncLog(
            sync_type="AUTO_API_SYNC", status="SUCCESS",
            records_processed=processed,
            error_message=f"source={source}, sold={sold}, batch={size}",
        )
        db.session.add(log)
        db.session.commit()
        return {
            "status": "SUCCESS",
            "processed": processed,
            "sold": sold,
            "source": source,
        }
    finally:
        seen_path.unlink(missing_ok=True)
