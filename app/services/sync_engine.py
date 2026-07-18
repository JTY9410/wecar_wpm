"""실시간 매물 동기화 (PRD §5.4). Upsert Listing, mark missing as sold, cache images."""
from app.extensions import db
from app.models import Listing, SyncLog
from app.services.api_client import ApiUnavailable, fetch_listings
from app.services.image_cache import cache_image


def _extract_image_url(item):
    info = item.get("ImageInfo")
    if isinstance(info, list) and info:
        return info[0].get("ImageUrl")
    return item.get("ImageUrl")


def sync_listings(fetch=fetch_listings, with_images=True):
    """Returns SyncLog-like dict. Never raises on partial failures."""
    try:
        data, source = fetch()
    except ApiUnavailable as exc:
        log = SyncLog(sync_type="AUTO_API_SYNC", status="FAIL",
                      records_processed=0, error_message=str(exc))
        db.session.add(log)
        db.session.commit()
        return {"status": "FAIL", "error": str(exc)}

    items = data.get("data") if isinstance(data, dict) else data
    items = items or []
    seen = set()
    for item in items:
        car_no = str(item.get("CarNo") or item.get("car_no") or "").strip()
        if not car_no:
            continue
        seen.add(car_no)
        listing = db.session.get(Listing, car_no) or Listing(car_no=car_no)
        listing.car_name = item.get("CarName")
        listing.maker_no = _to_int(item.get("MakerNo"))
        listing.car_year = _to_int(item.get("CarYear"))
        listing.car_km = _to_int(item.get("CarKm"))
        listing.car_amount_sale = _to_int(item.get("CarAmountSale"))
        listing.sido = item.get("Sido")
        listing.kind_name = item.get("KindName")
        listing.imported = item.get("Imported")
        listing.is_sold = False
        if with_images:
            url = cache_image(car_no, _extract_image_url(item))
            if url:
                listing.image_url = url
        db.session.add(listing)

    # Anything not in the latest feed is considered sold, but preserved.
    sold = 0
    for listing in Listing.query.filter(Listing.is_sold.is_(False)).all():
        if listing.car_no not in seen:
            listing.is_sold = True
            sold += 1

    log = SyncLog(sync_type="AUTO_API_SYNC", status="SUCCESS",
                  records_processed=len(seen),
                  error_message=f"source={source}, sold={sold}")
    db.session.add(log)
    db.session.commit()
    return {"status": "SUCCESS", "processed": len(seen), "sold": sold, "source": source}


def _to_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
