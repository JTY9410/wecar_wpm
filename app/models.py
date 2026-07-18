from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="USER")
    name = db.Column(db.String(80))
    phone = db.Column(db.String(32))
    affiliation = db.Column(db.String(128))
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self):
        return self.role == "ADMIN"


class Listing(db.Model):
    __tablename__ = "listing"

    car_no = db.Column(db.String(50), primary_key=True)
    car_name = db.Column(db.String(150))
    maker_no = db.Column(db.String(32))
    model_no = db.Column(db.String(32))
    mdetail_no = db.Column(db.String(32))
    grade_no = db.Column(db.String(32))
    gdetail_no = db.Column(db.String(32))
    car_year = db.Column(db.Integer)
    car_km = db.Column(db.Integer)
    car_amount_sale = db.Column(db.Integer)
    sido = db.Column(db.String(50))
    kind_name = db.Column(db.String(100))
    imported = db.Column(db.String(5))
    car_fuel = db.Column(db.String(32))
    car_awd = db.Column(db.String(16), default="미확인")
    image_url = db.Column(db.String(512))
    car_code = db.Column(db.String(255), index=True)
    is_sold = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    report = db.relationship(
        "GeminiReportCache", backref="listing", uselist=False, lazy=True
    )


# --- Vehicle hierarchy (car 참조 동일 5단 + year/fuel/awd on records) ---

class VehicleMaker(db.Model):
    __tablename__ = "vehicle_maker"
    maker_no = db.Column(db.String(32), primary_key=True)
    maker_name = db.Column(db.String(128), nullable=False, index=True)
    sort_no = db.Column(db.Integer)
    synced_at = db.Column(db.DateTime, default=utcnow)


class VehicleModel(db.Model):
    __tablename__ = "vehicle_model"
    model_no = db.Column(db.String(32), primary_key=True)
    maker_no = db.Column(db.String(32), db.ForeignKey("vehicle_maker.maker_no"), index=True)
    model_name = db.Column(db.String(128), nullable=False)
    sort_no = db.Column(db.Integer)


class VehicleModelDetail(db.Model):
    __tablename__ = "vehicle_model_detail"
    mdetail_no = db.Column(db.String(32), primary_key=True)
    model_no = db.Column(db.String(32), db.ForeignKey("vehicle_model.model_no"), index=True)
    mdetail_name = db.Column(db.String(256), nullable=False)
    sort_no = db.Column(db.Integer)
    st_year = db.Column(db.Integer)
    ed_year = db.Column(db.Integer)


class VehicleGrade(db.Model):
    __tablename__ = "vehicle_grade"
    grade_no = db.Column(db.String(32), primary_key=True)
    mdetail_no = db.Column(db.String(32), db.ForeignKey("vehicle_model_detail.mdetail_no"), index=True)
    grade_name = db.Column(db.String(128), nullable=False)
    sort_no = db.Column(db.Integer)


class VehicleGradeDetail(db.Model):
    __tablename__ = "vehicle_grade_detail"
    gdetail_no = db.Column(db.String(32), primary_key=True)
    grade_no = db.Column(db.String(32), db.ForeignKey("vehicle_grade.grade_no"), index=True)
    gdetail_name = db.Column(db.String(128), nullable=False)
    sort_no = db.Column(db.Integer)


class AuctionRecord(db.Model):
    """Weekly Excel raw lake. Hierarchy + car_code for wholesale API."""
    __tablename__ = "auction_record"

    id = db.Column(db.Integer, primary_key=True)
    week_no = db.Column(db.String(20), index=True)
    auction_date = db.Column(db.String(20))
    maker = db.Column(db.String(100))
    model_name = db.Column(db.String(150))
    mdetail_name = db.Column(db.String(150))
    grade_name = db.Column(db.String(128))
    gdetail_name = db.Column(db.String(255))
    car_name = db.Column(db.String(255))
    car_year = db.Column(db.Integer)
    car_km = db.Column(db.Integer)
    fuel = db.Column(db.String(50))
    awd = db.Column(db.String(16), default="미확인")
    imported = db.Column(db.String(10))
    start_price = db.Column(db.Integer)
    hope_price = db.Column(db.Integer)
    hammer_price = db.Column(db.Integer)
    accident_detail = db.Column(db.String(100))
    xx_exchange = db.Column(db.Text)
    w_panel = db.Column(db.Text)
    is_accident_free = db.Column(db.Boolean, default=False)
    maker_no = db.Column(db.String(32), index=True)
    model_no = db.Column(db.String(32), index=True)
    mdetail_no = db.Column(db.String(32), index=True)
    grade_no = db.Column(db.String(32), index=True)
    gdetail_no = db.Column(db.String(32), index=True)
    car_code = db.Column(db.String(255), index=True)
    km_bin = db.Column(db.String(40))
    raw_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)


class VehiclePriceTable(db.Model):
    __tablename__ = "vehicle_price_table"

    id = db.Column(db.Integer, primary_key=True)
    car_name = db.Column(db.String(255), index=True)
    fuel = db.Column(db.String(50))
    imported = db.Column(db.String(10))
    car_year = db.Column(db.Integer)
    avg_price = db.Column(db.Integer)


class MarketSummary(db.Model):
    """Aggregated wholesale grid — car 연동용 car_code 포함."""
    __tablename__ = "market_summary"

    id = db.Column(db.Integer, primary_key=True)
    car_code = db.Column(db.String(255), index=True)
    maker = db.Column(db.String(100), index=True)
    model_name = db.Column(db.String(150), index=True)
    mdetail_name = db.Column(db.String(150), index=True)
    grade_name = db.Column(db.String(128), index=True)
    gdetail_name = db.Column(db.String(255), index=True)
    car_name = db.Column(db.String(255))
    car_year = db.Column(db.Integer, index=True)
    fuel = db.Column(db.String(50), index=True)
    awd = db.Column(db.String(16), index=True)
    imported = db.Column(db.String(10))
    is_accident_free = db.Column(db.Boolean)
    km_bin = db.Column(db.String(40), index=True)
    start_avg = db.Column(db.Float)
    hammer_avg = db.Column(db.Float)
    mom_pct = db.Column(db.Float)
    sample_count = db.Column(db.Integer)
    week_no = db.Column(db.String(20), index=True)
    note = db.Column(db.String(255))


class GeminiReportCache(db.Model):
    __tablename__ = "gemini_report_cache"

    car_no = db.Column(db.String(50), db.ForeignKey("listing.car_no"), primary_key=True)
    report_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)


class SyncLog(db.Model):
    __tablename__ = "sync_log"

    id = db.Column(db.Integer, primary_key=True)
    sync_type = db.Column(db.String(50))
    status = db.Column(db.String(20))
    records_processed = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)


class TranslationCache(db.Model):
    __tablename__ = "translation_cache"

    id = db.Column(db.Integer, primary_key=True)
    source_hash = db.Column(db.String(64), index=True)
    source_text = db.Column(db.Text)
    lang = db.Column(db.String(5))
    translated_text = db.Column(db.Text)
    __table_args__ = (db.UniqueConstraint("source_hash", "lang", name="uq_trans"),)


class UploadHistory(db.Model):
    __tablename__ = "upload_history"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    week_no = db.Column(db.String(20))
    mode = db.Column(db.String(20))
    status = db.Column(db.String(20))
    rows_ok = db.Column(db.Integer, default=0)
    operator = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=utcnow)


class LLMConfig(db.Model):
    __tablename__ = "llm_config"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(20), unique=True)
    is_active = db.Column(db.Boolean, default=False)
    model_name = db.Column(db.String(80))
    api_key = db.Column(db.Text)
