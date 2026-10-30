"""Cascading filter + grid/matrix/samples queries over MarketSummary & AuctionRecord."""
import re
from collections import defaultdict

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


def _accident_grade_label(grade, is_free, lang="ko"):
    text = _clean(grade)
    if text:
        return text
    return _accident_label(is_free, lang)


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
    rows = db.session.execute(
        db.select(MarketSummary.maker).distinct()
        .where(MarketSummary.maker.isnot(None))
        .order_by(MarketSummary.maker)
    ).scalars().all()
    return _labeled(rows, lang)


def models(maker, lang="ko"):
    rows = db.session.execute(
        db.select(MarketSummary.model_name).distinct()
        .where(
            MarketSummary.maker == maker,
            MarketSummary.model_name.isnot(None),
        )
        .order_by(MarketSummary.model_name)
    ).scalars().all()
    return _labeled(rows, lang)


def mdetails(maker, model_name, lang="ko"):
    rows = db.session.execute(
        db.select(MarketSummary.mdetail_name).distinct()
        .where(
            MarketSummary.maker == maker,
            MarketSummary.model_name == model_name,
            MarketSummary.mdetail_name.isnot(None),
        )
        .order_by(MarketSummary.mdetail_name)
    ).scalars().all()
    return _labeled(rows, lang)


def grades(maker, model_name=None, mdetail=None, lang="ko"):
    stmt = (
        db.select(MarketSummary.grade_name).distinct()
        .where(MarketSummary.maker == maker, MarketSummary.grade_name.isnot(None))
    )
    if model_name:
        stmt = stmt.where(MarketSummary.model_name == model_name)
    if mdetail:
        stmt = stmt.where(MarketSummary.mdetail_name == mdetail)
    rows = db.session.execute(stmt.order_by(MarketSummary.grade_name)).scalars().all()
    return _labeled(rows, lang)


def gdetails(maker, model_name=None, mdetail=None, grade=None, lang="ko"):
    stmt = (
        db.select(MarketSummary.gdetail_name).distinct()
        .where(MarketSummary.maker == maker, MarketSummary.gdetail_name.isnot(None))
    )
    if model_name:
        stmt = stmt.where(MarketSummary.model_name == model_name)
    if mdetail:
        stmt = stmt.where(MarketSummary.mdetail_name == mdetail)
    if grade:
        stmt = stmt.where(MarketSummary.grade_name == grade)
    rows = db.session.execute(stmt.order_by(MarketSummary.gdetail_name)).scalars().all()
    return _labeled(rows, lang)


def years(maker, model_name=None, mdetail=None):
    stmt = (
        db.select(MarketSummary.car_year).distinct()
        .where(MarketSummary.maker == maker, MarketSummary.car_year.isnot(None))
    )
    if model_name:
        stmt = stmt.where(MarketSummary.model_name == model_name)
    if mdetail:
        stmt = stmt.where(MarketSummary.mdetail_name == mdetail)
    return db.session.execute(stmt.order_by(MarketSummary.car_year.desc())).scalars().all()


def fuels(maker=None, lang="ko"):
    stmt = db.select(MarketSummary.fuel).distinct().where(MarketSummary.fuel.isnot(None))
    if maker:
        stmt = stmt.where(MarketSummary.maker == maker)
    rows = db.session.execute(stmt.order_by(MarketSummary.fuel)).scalars().all()
    return _labeled(rows, lang)


def _filter_summary(stmt, maker=None, model_name=None, mdetail_name=None, grade_name=None,
                    gdetail_name=None, car_name=None, car_year=None, fuel=None, awd=None,
                    km_bin=None, is_accident_free=None, accident_grade=None, q=None):
    if maker:
        stmt = stmt.where(MarketSummary.maker == maker)
    if model_name:
        stmt = stmt.where(MarketSummary.model_name == model_name)
    if mdetail_name:
        stmt = stmt.where(MarketSummary.mdetail_name == mdetail_name)
    if grade_name:
        stmt = stmt.where(MarketSummary.grade_name == grade_name)
    if gdetail_name:
        stmt = stmt.where(MarketSummary.gdetail_name == gdetail_name)
    word = (car_name or q or "").strip()
    if word:
        like = f"%{word}%"
        stmt = stmt.where(db.or_(
            MarketSummary.car_name.ilike(like),
            MarketSummary.model_name.ilike(like),
            MarketSummary.mdetail_name.ilike(like),
            MarketSummary.gdetail_name.ilike(like),
        ))
    if car_year not in (None, "") and _safe_int(car_year) is not None:
        stmt = stmt.where(MarketSummary.car_year == _safe_int(car_year))
    if fuel:
        stmt = stmt.where(MarketSummary.fuel == fuel)
    if awd:
        stmt = stmt.where(MarketSummary.awd == awd)
    if km_bin:
        stmt = stmt.where(MarketSummary.km_bin == km_bin)
    if accident_grade:
        stmt = stmt.where(MarketSummary.accident_grade == accident_grade)
    if is_accident_free is not None:
        stmt = stmt.where(MarketSummary.is_accident_free == bool(is_accident_free))
    return stmt


def grid(maker=None, model_name=None, mdetail_name=None, car_name=None,
         car_year=None, fuel=None, awd=None, grade_name=None, gdetail_name=None,
         q=None, lang="ko"):
    stmt = _filter_summary(
        db.select(MarketSummary), maker=maker, model_name=model_name,
        mdetail_name=mdetail_name, grade_name=grade_name,
        gdetail_name=gdetail_name, car_name=car_name, q=q,
        car_year=car_year, fuel=fuel, awd=awd,
    )
    stmt = (
        stmt.where(
            MarketSummary.hammer_avg.isnot(None),
            MarketSummary.hammer_avg > 0,
        )
        .order_by(MarketSummary.car_year.desc(), MarketSummary.km_bin)
        .limit(500)
    )
    rows = db.session.execute(stmt).scalars().all()

    def _tr(value):
        # polish=False: 그리드 N건마다 Gemini를 부르면 워커 타임아웃 발생
        return translate(value, lang, polish=False) if value and lang != "ko" else value

    # value 필드는 한국어 원문(후속 필터/샘플 API용), *_label 은 화면 표시용 번역.
    result = []
    for r in rows:
        mk = _clean(r.maker)
        md = _clean(r.model_name)
        mt = _clean(r.mdetail_name)
        gr = _clean(r.grade_name)
        gd = _clean(r.gdetail_name)
        cn = _clean(r.car_name)
        fl = _clean(r.fuel)
        grade = _accident_grade_label(
            getattr(r, "accident_grade", None), r.is_accident_free, lang,
        )
        result.append({
            "car_code": _clean(r.car_code),
            "maker": mk, "maker_label": _tr(mk),
            "model_name": md, "model_name_label": _tr(md),
            "mdetail_name": mt, "mdetail_name_label": _tr(mt),
            "grade_name": gr, "grade_name_label": _tr(gr),
            "gdetail_name": gd, "gdetail_name_label": _tr(gd),
            "car_name": cn, "car_name_label": _tr(cn),
            "car_year": r.car_year,
            "fuel": fl, "fuel_label": _tr(fl),
            "awd": _clean(r.awd),
            "imported": _clean(r.imported),
            "accident_grade": grade,
            "accident_grade_label": _tr(grade) if grade else grade,
            "is_accident_free": grade if grade else _accident_label(r.is_accident_free, lang),
            "is_accident_free_flag": bool(r.is_accident_free),
            "km_bin": _clean(r.km_bin), "start_avg": r.start_avg, "hammer_avg": r.hammer_avg,
            "wow_pct": r.mom_pct, "mom_pct": r.mom_pct,  # mom_pct=전주대비(%) alias
            "sample_count": r.sample_count, "week_no": _clean(r.week_no),
            "note": _tr(_clean(r.note)),
        })
    return result


def matrix(maker=None, model_name=None, mdetail_name=None, grade_name=None,
           gdetail_name=None, fuel=None, awd=None, accident_free=None):
    """연식 × 주행구간 매트릭스 — 낙찰가(hammer_price) 평균."""
    if not maker:
        return {"years": [], "buckets": [], "matrix": {}, "counts": {}, "total_samples": 0,
                "price_basis": "hammer"}

    stmt = db.select(AuctionRecord).where(
        AuctionRecord.hammer_price.isnot(None),
        AuctionRecord.hammer_price > 0,
        AuctionRecord.maker == maker,
    )
    if model_name:
        stmt = stmt.where(AuctionRecord.model_name == model_name)
    if mdetail_name:
        stmt = stmt.where(AuctionRecord.mdetail_name == mdetail_name)
    if grade_name:
        stmt = stmt.where(AuctionRecord.grade_name == grade_name)
    if gdetail_name:
        stmt = stmt.where(AuctionRecord.gdetail_name == gdetail_name)
    if fuel:
        stmt = stmt.where(AuctionRecord.fuel == fuel)
    if awd:
        stmt = stmt.where(AuctionRecord.awd == awd)
    if accident_free == "1":
        stmt = stmt.where(AuctionRecord.is_accident_free.is_(True))
    elif accident_free == "0":
        stmt = stmt.where(AuctionRecord.is_accident_free.is_(False))

    rows = db.session.execute(stmt).scalars().all()
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
    stmt = db.select(AuctionRecord).where(
        AuctionRecord.hammer_price.isnot(None),
        AuctionRecord.hammer_price > 0,
    )
    if maker:
        stmt = stmt.where(AuctionRecord.maker == maker)
    if model_name:
        stmt = stmt.where(AuctionRecord.model_name == model_name)
    if mdetail_name:
        stmt = stmt.where(AuctionRecord.mdetail_name == mdetail_name)
    if grade_name:
        stmt = stmt.where(AuctionRecord.grade_name == grade_name)
    if gdetail_name:
        stmt = stmt.where(AuctionRecord.gdetail_name == gdetail_name)
    if car_year not in (None, "") and _safe_int(car_year) is not None:
        stmt = stmt.where(AuctionRecord.car_year == _safe_int(car_year))
    if km_bin:
        stmt = stmt.where(AuctionRecord.km_bin == km_bin)
    if fuel:
        stmt = stmt.where(AuctionRecord.fuel == fuel)
    if awd:
        stmt = stmt.where(AuctionRecord.awd == awd)
    if accident_free == "1":
        stmt = stmt.where(AuctionRecord.is_accident_free.is_(True))
    elif accident_free == "0":
        stmt = stmt.where(AuctionRecord.is_accident_free.is_(False))

    rows = db.session.execute(
        stmt.order_by(AuctionRecord.hammer_price.desc()).limit(limit)
    ).scalars().all()

    def _tr(value):
        return translate(value, lang, polish=False) if value and lang != "ko" else value

    items = []
    for r in rows:
        grade = _accident_grade_label(
            getattr(r, "accident_grade", None), r.is_accident_free, lang,
        )
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
            "accident_status": grade,
            "accident_grade": grade,
            "accident_detail": detail,
            "xx_exchange": _clean(r.xx_exchange),
            "w_panel": _clean(r.w_panel),
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
    stmt = db.select(AuctionRecord).where(
        AuctionRecord.hammer_price.isnot(None),
        AuctionRecord.hammer_price > 0,
        AuctionRecord.week_no.isnot(None),
    )
    if maker:
        stmt = stmt.where(AuctionRecord.maker == maker)
    if model_name:
        stmt = stmt.where(AuctionRecord.model_name == model_name)
    if mdetail_name:
        stmt = stmt.where(AuctionRecord.mdetail_name == mdetail_name)
    if grade_name:
        stmt = stmt.where(AuctionRecord.grade_name == grade_name)
    if gdetail_name:
        stmt = stmt.where(AuctionRecord.gdetail_name == gdetail_name)
    if car_year not in (None, "") and _safe_int(car_year) is not None:
        stmt = stmt.where(AuctionRecord.car_year == _safe_int(car_year))
    if fuel:
        stmt = stmt.where(AuctionRecord.fuel == fuel)
    if awd:
        stmt = stmt.where(AuctionRecord.awd == awd)

    rows = db.session.execute(stmt).scalars().all()
    by_week = defaultdict(list)
    for r in rows:
        by_week[r.week_no].append(r.hammer_price)

    week_keys = sorted(by_week.keys())[-max(1, int(weeks)):]
    return [{
        "week_no": w,
        "avg_price": round(sum(by_week[w]) / len(by_week[w]), 1),
        "sample_count": len(by_week[w]),
    } for w in week_keys]


def weeks():
    rows = db.session.execute(
        db.select(AuctionRecord.week_no).distinct()
        .where(AuctionRecord.week_no.isnot(None))
        .order_by(AuctionRecord.week_no)
    ).scalars().all()
    return [w for w in rows if w]


def _weeks_in_range(week_from, week_to):
    all_w = weeks()
    if not all_w:
        return []
    wf = week_from or all_w[0]
    wt = week_to or all_w[-1]
    if wf > wt:
        wf, wt = wt, wf
    return [w for w in all_w if wf <= w <= wt]


def full_grid(week_from=None, week_to=None, maker=None, model_name=None,
              mdetail_name=None, grade_name=None, gdetail_name=None,
              car_year=None, fuel=None, q=None, lang="ko", limit=2000):
    """경매차수 구간의 출품 시세를 트림·주행구간·사고여부로 집계."""
    selected = _weeks_in_range(week_from, week_to)
    if not selected:
        return {"ok": True, "weeks": [], "rows": [], "count": 0}

    stmt = (
        db.select(
            AuctionRecord.maker,
            AuctionRecord.model_name,
            AuctionRecord.mdetail_name,
            AuctionRecord.grade_name,
            AuctionRecord.gdetail_name,
            AuctionRecord.car_year,
            AuctionRecord.fuel,
            AuctionRecord.km_bin,
            AuctionRecord.is_accident_free,
            db.func.avg(AuctionRecord.hammer_price).label("hammer_avg"),
            db.func.count().label("sample_count"),
        )
        .where(
            AuctionRecord.hammer_price.isnot(None),
            AuctionRecord.hammer_price > 0,
            AuctionRecord.week_no.in_(selected),
        )
        .group_by(
            AuctionRecord.maker,
            AuctionRecord.model_name,
            AuctionRecord.mdetail_name,
            AuctionRecord.grade_name,
            AuctionRecord.gdetail_name,
            AuctionRecord.car_year,
            AuctionRecord.fuel,
            AuctionRecord.km_bin,
            AuctionRecord.is_accident_free,
        )
    )
    if maker:
        stmt = stmt.where(AuctionRecord.maker == maker)
    if model_name:
        stmt = stmt.where(AuctionRecord.model_name == model_name)
    if mdetail_name:
        stmt = stmt.where(AuctionRecord.mdetail_name == mdetail_name)
    if grade_name:
        stmt = stmt.where(AuctionRecord.grade_name == grade_name)
    if gdetail_name:
        stmt = stmt.where(AuctionRecord.gdetail_name == gdetail_name)
    if car_year not in (None, "") and _safe_int(car_year) is not None:
        stmt = stmt.where(AuctionRecord.car_year == _safe_int(car_year))
    if fuel:
        stmt = stmt.where(AuctionRecord.fuel == fuel)
    word = (q or "").strip()
    if word:
        like = f"%{word}%"
        stmt = stmt.where(db.or_(
            AuctionRecord.maker.ilike(like),
            AuctionRecord.model_name.ilike(like),
            AuctionRecord.mdetail_name.ilike(like),
            AuctionRecord.grade_name.ilike(like),
            AuctionRecord.gdetail_name.ilike(like),
            AuctionRecord.fuel.ilike(like),
            db.cast(AuctionRecord.car_year, db.String).like(like),
        ))

    stmt = stmt.order_by(
        AuctionRecord.maker,
        AuctionRecord.model_name,
        AuctionRecord.gdetail_name,
        AuctionRecord.car_year.desc(),
        AuctionRecord.km_bin,
    ).limit(limit)
    rows = db.session.execute(stmt).all()

    def _tr(value):
        return translate(value, lang, polish=False) if value and lang != "ko" else value

    result = []
    for r in rows:
        acc_free = bool(r.is_accident_free)
        result.append({
            "maker": _clean(r.maker), "maker_label": _tr(_clean(r.maker)),
            "model_name": _clean(r.model_name), "model_name_label": _tr(_clean(r.model_name)),
            "mdetail_name": _clean(r.mdetail_name), "mdetail_name_label": _tr(_clean(r.mdetail_name)),
            "grade_name": _clean(r.grade_name), "grade_name_label": _tr(_clean(r.grade_name)),
            "gdetail_name": _clean(r.gdetail_name), "gdetail_name_label": _tr(_clean(r.gdetail_name)),
            "car_year": r.car_year,
            "fuel": _clean(r.fuel), "fuel_label": _tr(_clean(r.fuel)),
            "km_bin": _clean(r.km_bin),
            "is_accident_free": _accident_label(acc_free, lang),
            "is_accident_free_flag": acc_free,
            "hammer_avg": round(float(r.hammer_avg), 1) if r.hammer_avg is not None else None,
            "sample_count": int(r.sample_count or 0),
        })
    return {"ok": True, "weeks": selected, "rows": result, "count": len(result)}


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
