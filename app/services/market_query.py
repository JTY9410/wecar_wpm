"""Cascading filter + grid queries over MarketSummary."""
import re

from sqlalchemy import distinct

from app.extensions import db
from app.models import MarketSummary

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _clean(val):
    if val is None:
        return None
    if isinstance(val, str):
        return _CTRL.sub("", val)
    return val


def makers():
    rows = db.session.query(distinct(MarketSummary.maker)).filter(
        MarketSummary.maker.isnot(None)).order_by(MarketSummary.maker).all()
    return [_clean(r[0]) for r in rows]


def models(maker):
    rows = db.session.query(distinct(MarketSummary.model_name)).filter(
        MarketSummary.maker == maker,
        MarketSummary.model_name.isnot(None)).order_by(MarketSummary.model_name).all()
    return [_clean(r[0]) for r in rows]


def mdetails(maker, model_name):
    rows = db.session.query(distinct(MarketSummary.mdetail_name)).filter(
        MarketSummary.maker == maker, MarketSummary.model_name == model_name,
        MarketSummary.mdetail_name.isnot(None)).order_by(MarketSummary.mdetail_name).all()
    return [_clean(r[0]) for r in rows]


def years(maker, model_name=None, mdetail=None):
    q = db.session.query(distinct(MarketSummary.car_year)).filter(
        MarketSummary.maker == maker, MarketSummary.car_year.isnot(None))
    if model_name:
        q = q.filter(MarketSummary.model_name == model_name)
    if mdetail:
        q = q.filter(MarketSummary.mdetail_name == mdetail)
    return [r[0] for r in q.order_by(MarketSummary.car_year.desc()).all()]


def fuels(maker=None):
    q = db.session.query(distinct(MarketSummary.fuel)).filter(MarketSummary.fuel.isnot(None))
    if maker:
        q = q.filter(MarketSummary.maker == maker)
    return [_clean(r[0]) for r in q.order_by(MarketSummary.fuel).all()]


def grid(maker=None, model_name=None, mdetail_name=None, car_name=None,
         car_year=None, fuel=None, awd=None):
    q = MarketSummary.query
    if maker:
        q = q.filter(MarketSummary.maker == maker)
    if model_name:
        q = q.filter(MarketSummary.model_name == model_name)
    if mdetail_name:
        q = q.filter(MarketSummary.mdetail_name == mdetail_name)
    if car_name:
        q = q.filter(MarketSummary.car_name == car_name)
    if car_year:
        q = q.filter(MarketSummary.car_year == int(car_year))
    if fuel:
        q = q.filter(MarketSummary.fuel == fuel)
    if awd:
        q = q.filter(MarketSummary.awd == awd)
    rows = q.order_by(MarketSummary.car_year.desc(), MarketSummary.km_bin).limit(500).all()
    return [{
        "car_code": _clean(r.car_code), "maker": _clean(r.maker),
        "model_name": _clean(r.model_name), "mdetail_name": _clean(r.mdetail_name),
        "grade_name": _clean(r.grade_name), "gdetail_name": _clean(r.gdetail_name),
        "car_name": _clean(r.car_name), "car_year": r.car_year,
        "fuel": _clean(r.fuel), "awd": _clean(r.awd),
        "imported": _clean(r.imported),
        "is_accident_free": "무사고" if r.is_accident_free else "사고차",
        "km_bin": _clean(r.km_bin), "start_avg": r.start_avg, "hammer_avg": r.hammer_avg,
        "mom_pct": r.mom_pct, "sample_count": r.sample_count, "note": _clean(r.note),
    } for r in rows]


# backward-compat aliases used by market routes
def car_names(maker, model_name):
    return mdetails(maker, model_name)
