"""Cascading filter + grid/matrix/samples queries over MarketSummary & AuctionRecord."""
import re
from collections import defaultdict

from sqlalchemy import distinct

from app.extensions import db
from app.models import AuctionRecord, MarketSummary
from app.services.i18n_translate import load_pack, translate

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _safe_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _clean(val):
    if val is None:
        return None
    if isinstance(val, str):
        return _CTRL.sub("", val)
    return val


def _accident_label(is_free, lang="ko"):
    pack = load_pack(lang)
    if is_free:
        return pack.get("accident_free", "무사고")
    return pack.get("accident_damaged", "사고차")


def _labeled(values, lang="ko"):
    """필터 value는 한국어 원문 유지, label만 번역.

    remote=False: 페이지 로드/캐스케이드에서 Google·Gemini 동기 호출로
    gunicorn 워커가 타임아웃되지 않도록 용어집·캐시만 사용한다.
    """
    out = []
    for v in values:
        if v is None or v == "":
            continue
        cleaned = _clean(v)
        label = (
            translate(cleaned, lang, remote=False)
            if cleaned and lang != "ko"
            else cleaned
        )
        out.append({"value": cleaned, "label": label})
    return out


def makers(lang="ko"):
    rows = db.session.query(distinct(MarketSummary.maker)).filter(
        MarketSummary.maker.isnot(None)).order_by(MarketSummary.maker).all()
    return _labeled([r[0] for r in rows], lang)


def models(maker, lang="ko"):
    rows = db.session.query(distinct(MarketSummary.model_name)).filter(
        MarketSummary.maker == maker,
        MarketSummary.model_name.isnot(None)).order_by(MarketSummary.model_name).all()
    return _labeled([r[0] for r in rows], lang)


def mdetails(maker, model_name, lang="ko"):
    rows = db.session.query(distinct(MarketSummary.mdetail_name)).filter(
        MarketSummary.maker == maker, MarketSummary.model_name == model_name,
        MarketSummary.mdetail_name.isnot(None)).order_by(MarketSummary.mdetail_name).all()
    return _labeled([r[0] for r in rows], lang)


def grades(maker, model_name=None, mdetail=None, lang="ko"):
    q = db.session.query(distinct(MarketSummary.grade_name)).filter(
        MarketSummary.maker == maker, MarketSummary.grade_name.isnot(None))
    if model_name:
        q = q.filter(MarketSummary.model_name == model_name)
    if mdetail:
        q = q.filter(MarketSummary.mdetail_name == mdetail)
    return _labeled([r[0] for r in q.order_by(MarketSummary.grade_name).all()], lang)


def gdetails(maker, model_name=None, mdetail=None, grade=None, lang="ko"):
    q = db.session.query(distinct(MarketSummary.gdetail_name)).filter(
        MarketSummary.maker == maker, MarketSummary.gdetail_name.isnot(None))
    if model_name:
        q = q.filter(MarketSummary.model_name == model_name)
    if mdetail:
        q = q.filter(MarketSummary.mdetail_name == mdetail)
    if grade:
        q = q.filter(MarketSummary.grade_name == grade)
    return _labeled([r[0] for r in q.order_by(MarketSummary.gdetail_name).all()], lang)


def years(maker, model_name=None, mdetail=None):
    q = db.session.query(distinct(MarketSummary.car_year)).filter(
        MarketSummary.maker == maker, MarketSummary.car_year.isnot(None))
    if model_name:
        q = q.filter(MarketSummary.model_name == model_name)
    if mdetail:
        q = q.filter(MarketSummary.mdetail_name == mdetail)
    return [r[0] for r in q.order_by(MarketSummary.car_year.desc()).all()]


def fuels(maker=None, lang="ko"):
    q = db.session.query(distinct(MarketSummary.fuel)).filter(MarketSummary.fuel.isnot(None))
    if maker:
        q = q.filter(MarketSummary.maker == maker)
    return _labeled([r[0] for r in q.order_by(MarketSummary.fuel).all()], lang)


def _filter_summary(q, maker=None, model_name=None, mdetail_name=None, grade_name=None,
                    gdetail_name=None, car_year=None, fuel=None, awd=None, km_bin=None,
                    is_accident_free=None):
    if maker:
        q = q.filter(MarketSummary.maker == maker)
    if model_name:
        q = q.filter(MarketSummary.model_name == model_name)
    if mdetail_name:
        q = q.filter(MarketSummary.mdetail_name == mdetail_name)
    if grade_name:
        q = q.filter(MarketSummary.grade_name == grade_name)
    if gdetail_name:
        q = q.filter(MarketSummary.gdetail_name == gdetail_name)
    if car_year not in (None, "") and _safe_int(car_year) is not None:
        q = q.filter(MarketSummary.car_year == _safe_int(car_year))
    if fuel:
        q = q.filter(MarketSummary.fuel == fuel)
    if awd:
        q = q.filter(MarketSummary.awd == awd)
    if km_bin:
        q = q.filter(MarketSummary.km_bin == km_bin)
    if is_accident_free is not None:
        q = q.filter(MarketSummary.is_accident_free == bool(is_accident_free))
    return q


def grid(maker=None, model_name=None, mdetail_name=None, car_name=None,
         car_year=None, fuel=None, awd=None, grade_name=None, gdetail_name=None,
         lang="ko"):
    q = _filter_summary(
        MarketSummary.query, maker=maker, model_name=model_name,
        mdetail_name=mdetail_name or car_name, grade_name=grade_name,
        gdetail_name=gdetail_name, car_year=car_year, fuel=fuel, awd=awd,
    )
    rows = q.filter(
        MarketSummary.hammer_avg.isnot(None),
        MarketSummary.hammer_avg > 0,
    ).order_by(MarketSummary.car_year.desc(), MarketSummary.km_bin).limit(500).all()

    def _tr(value):
        # polish=False: 그리드 N건마다 Gemini를 부르면 워커 타임아웃 발생
        return translate(value, lang, polish=False) if value and lang != "ko" else value

    # value 필드는 한국어 원문(후속 필터/샘플 API용), *_label 은 화면 표시용 번역.
    result = []
    for r in rows:
        maker = _clean(r.maker)
        model_name = _clean(r.model_name)
        mdetail_name = _clean(r.mdetail_name)
        grade_name = _clean(r.grade_name)
        gdetail_name = _clean(r.gdetail_name)
        car_name = _clean(r.car_name)
        fuel = _clean(r.fuel)
        result.append({
            "car_code": _clean(r.car_code),
            "maker": maker, "maker_label": _tr(maker),
            "model_name": model_name, "model_name_label": _tr(model_name),
            "mdetail_name": mdetail_name, "mdetail_name_label": _tr(mdetail_name),
            "grade_name": grade_name, "grade_name_label": _tr(grade_name),
            "gdetail_name": gdetail_name, "gdetail_name_label": _tr(gdetail_name),
            "car_name": car_name, "car_name_label": _tr(car_name),
            "car_year": r.car_year,
            "fuel": fuel, "fuel_label": _tr(fuel),
            "awd": _clean(r.awd),
            "imported": _clean(r.imported),
            "is_accident_free": _accident_label(r.is_accident_free, lang),
            "is_accident_free_flag": bool(r.is_accident_free),
            "km_bin": _clean(r.km_bin), "start_avg": r.start_avg, "hammer_avg": r.hammer_avg,
            "wow_pct": r.mom_pct, "mom_pct": r.mom_pct,  # mom_pct=전주대비(%) alias
            "sample_count": r.sample_count, "note": _tr(_clean(r.note)),
        })
    return result


def matrix(maker=None, model_name=None, mdetail_name=None, grade_name=None,
           gdetail_name=None, fuel=None, awd=None, accident_free=None):
    """연식 × 주행구간 매트릭스 — 낙찰가(hammer_price) 평균."""
    if not maker:
        return {"years": [], "buckets": [], "matrix": {}, "counts": {}, "total_samples": 0,
                "price_basis": "hammer"}

    q = AuctionRecord.query.filter(
        AuctionRecord.hammer_price.isnot(None),
        AuctionRecord.hammer_price > 0,
        AuctionRecord.maker == maker,
    )
    if model_name:
        q = q.filter(AuctionRecord.model_name == model_name)
    if mdetail_name:
        q = q.filter(AuctionRecord.mdetail_name == mdetail_name)
    if grade_name:
        q = q.filter(AuctionRecord.grade_name == grade_name)
    if gdetail_name:
        q = q.filter(AuctionRecord.gdetail_name == gdetail_name)
    if fuel:
        q = q.filter(AuctionRecord.fuel == fuel)
    if awd:
        q = q.filter(AuctionRecord.awd == awd)
    if accident_free == "1":
        q = q.filter(AuctionRecord.is_accident_free.is_(True))
    elif accident_free == "0":
        q = q.filter(AuctionRecord.is_accident_free.is_(False))

    rows = q.all()
    if not rows:
        return {"years": [], "buckets": [], "matrix": {}, "counts": {}, "total_samples": 0,
                "price_basis": "hammer"}

    prices = defaultdict(lambda: defaultdict(list))
    buckets_set = set()
    years_set = set()
    for r in rows:
        if r.car_year is None or not r.km_bin:
            continue
        years_set.add(r.car_year)
        buckets_set.add(r.km_bin)
        prices[r.car_year][r.km_bin].append(r.hammer_price)

    def _bin_sort_key(label):
        m = re.search(r"([\d.]+)", str(label) or "")
        return float(m.group(1)) if m else 0

    years = sorted(years_set, reverse=True)
    buckets = sorted(buckets_set, key=_bin_sort_key)
    mat = {}
    cnt = {}
    total = 0
    for y in years:
        mat[y] = {}
        cnt[y] = {}
        for b in buckets:
            vals = prices[y][b]
            n = len(vals)
            cnt[y][b] = n
            total += n
            mat[y][b] = round(sum(vals) / n, 1) if n else None

    return {
        "years": years,
        "buckets": buckets,
        "matrix": mat,
        "counts": cnt,
        "total_samples": total,
        "price_basis": "hammer",
        "maker": maker,
        "model_name": model_name,
        "mdetail_name": mdetail_name,
        "grade_name": grade_name,
        "gdetail_name": gdetail_name,
        "fuel": fuel,
        "awd": awd,
    }


def samples(maker=None, model_name=None, mdetail_name=None, grade_name=None,
            gdetail_name=None, car_year=None, km_bin=None, fuel=None, awd=None,
            accident_free=None, lang="ko", limit=200):
    """세부내역 — 낙찰가 > 0 인 경매 원장만."""
    q = AuctionRecord.query.filter(
        AuctionRecord.hammer_price.isnot(None),
        AuctionRecord.hammer_price > 0,
    )
    if maker:
        q = q.filter(AuctionRecord.maker == maker)
    if model_name:
        q = q.filter(AuctionRecord.model_name == model_name)
    if mdetail_name:
        q = q.filter(AuctionRecord.mdetail_name == mdetail_name)
    if grade_name:
        q = q.filter(AuctionRecord.grade_name == grade_name)
    if gdetail_name:
        q = q.filter(AuctionRecord.gdetail_name == gdetail_name)
    if car_year not in (None, "") and _safe_int(car_year) is not None:
        q = q.filter(AuctionRecord.car_year == _safe_int(car_year))
    if km_bin:
        q = q.filter(AuctionRecord.km_bin == km_bin)
    if fuel:
        q = q.filter(AuctionRecord.fuel == fuel)
    if awd:
        q = q.filter(AuctionRecord.awd == awd)
    if accident_free == "1":
        q = q.filter(AuctionRecord.is_accident_free.is_(True))
    elif accident_free == "0":
        q = q.filter(AuctionRecord.is_accident_free.is_(False))

    rows = q.order_by(AuctionRecord.hammer_price.desc()).limit(limit).all()

    def _tr(value):
        return translate(value, lang, polish=False) if value and lang != "ko" else value

    items = []
    for r in rows:
        acc = _accident_label(r.is_accident_free, lang)
        detail = _tr(_clean(r.accident_detail) or "")
        items.append({
            "id": r.id,
            "car_name": _tr(_clean(r.car_name)),
            "maker": _tr(_clean(r.maker)),
            "model_name": _tr(_clean(r.model_name)),
            "mdetail_name": _tr(_clean(r.mdetail_name)),
            "grade_name": _tr(_clean(r.grade_name)),
            "gdetail_name": _tr(_clean(r.gdetail_name)),
            "car_year": r.car_year,
            "fuel": _tr(_clean(r.fuel)),
            "awd": _clean(r.awd),
            "car_km": r.car_km,
            "km_bin": _clean(r.km_bin),
            "start_price": r.start_price,
            "hope_price": r.hope_price,
            "hammer_price": r.hammer_price,
            "imported": _clean(r.imported),
            "accident_status": acc,
            "accident_detail": detail,
            "auction_date": _clean(r.auction_date),
            "week_no": _clean(r.week_no),
        })
    return {"ok": True, "count": len(items), "items": items, "price_basis": "hammer"}


# backward-compat aliases used by market routes
def car_names(maker, model_name, lang="ko"):
    return mdetails(maker, model_name, lang=lang)


def price_trend(maker=None, model_name=None, mdetail_name=None, grade_name=None,
                 gdetail_name=None, car_year=None, fuel=None, awd=None, weeks=8):
    """차종 조합의 주차별(week_no) 낙찰가 평균 추이. km_bin은 주차별 표본 수 확보를 위해 제외."""
    q = AuctionRecord.query.filter(
        AuctionRecord.hammer_price.isnot(None),
        AuctionRecord.hammer_price > 0,
        AuctionRecord.week_no.isnot(None),
    )
    if maker:
        q = q.filter(AuctionRecord.maker == maker)
    if model_name:
        q = q.filter(AuctionRecord.model_name == model_name)
    if mdetail_name:
        q = q.filter(AuctionRecord.mdetail_name == mdetail_name)
    if grade_name:
        q = q.filter(AuctionRecord.grade_name == grade_name)
    if gdetail_name:
        q = q.filter(AuctionRecord.gdetail_name == gdetail_name)
    if car_year not in (None, "") and _safe_int(car_year) is not None:
        q = q.filter(AuctionRecord.car_year == _safe_int(car_year))
    if fuel:
        q = q.filter(AuctionRecord.fuel == fuel)
    if awd:
        q = q.filter(AuctionRecord.awd == awd)

    rows = q.all()
    by_week = defaultdict(list)
    for r in rows:
        by_week[r.week_no].append(r.hammer_price)

    week_keys = sorted(by_week.keys())[-max(1, int(weeks)):]
    return [{
        "week_no": w,
        "avg_price": round(sum(by_week[w]) / len(by_week[w]), 1),
        "sample_count": len(by_week[w]),
    } for w in week_keys]


def forecast_from_trend(trend):
    """주차별 추이를 바탕으로 금주 예상가를 산출 (AI가 아닌 통계적 계산, PRD §2 준수).

    최근 3개 구간의 전주대비 변동률을 최근일수록 높은 가중치로 반영해
    다음 낙찰가를 추정한다. 변동폭은 ±15%로 제한해 소표본 노이즈를 억제한다.
    """
    if not trend:
        return {"ok": False}

    latest = trend[-1]
    current_avg = latest["avg_price"]
    if len(trend) < 2:
        return {
            "ok": True, "current_avg": current_avg, "expected_price": current_avg,
            "expected_pct": 0.0, "basis": "single_week",
        }

    pct_changes = []
    for i in range(1, len(trend)):
        prev = trend[i - 1]["avg_price"]
        if prev:
            pct_changes.append((trend[i]["avg_price"] - prev) / prev)
    recent = pct_changes[-3:]
    weights = list(range(1, len(recent) + 1))
    trend_pct = sum(p * w for p, w in zip(recent, weights)) / sum(weights)
    trend_pct = max(-0.15, min(0.15, trend_pct))

    expected_price = round(current_avg * (1 + trend_pct), 1)
    return {
        "ok": True, "current_avg": current_avg, "expected_price": expected_price,
        "expected_pct": round(trend_pct * 100, 1), "basis": "trend",
    }
