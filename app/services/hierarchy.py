"""엑셀/시세 데이터에서 차량 계층 코드를 생성·업서트 (car 체계 준용)."""
from app.extensions import db
from app.models import (
    VehicleGrade, VehicleGradeDetail, VehicleMaker, VehicleModel, VehicleModelDetail,
)
from app.services.car_code import slug


def _code(prefix, *parts):
    body = slug("|".join(str(p or "") for p in parts))
    return f"{prefix}_{body}"[:32]


def ensure_hierarchy(maker, model, mdetail, grade, gdetail):
    """이름 기반 계층 코드 보장. Returns dict of *_no and names."""
    maker = (maker or "").strip() or "미상"
    model = (model or "").strip() or "미상"
    mdetail = (mdetail or model or "").strip() or "미상"
    grade = (grade or "기본").strip() or "기본"
    gdetail = (gdetail or "").strip() or grade

    maker_no = _code("mk", maker)
    model_no = _code("md", maker, model)
    mdetail_no = _code("mt", maker, model, mdetail)
    grade_no = _code("gr", maker, model, mdetail, grade)
    gdetail_no = _code("gd", maker, model, mdetail, grade, gdetail)

    if not db.session.get(VehicleMaker, maker_no):
        db.session.add(VehicleMaker(maker_no=maker_no, maker_name=maker))
    if not db.session.get(VehicleModel, model_no):
        db.session.add(VehicleModel(model_no=model_no, maker_no=maker_no, model_name=model))
    if not db.session.get(VehicleModelDetail, mdetail_no):
        db.session.add(VehicleModelDetail(
            mdetail_no=mdetail_no, model_no=model_no, mdetail_name=mdetail))
    if not db.session.get(VehicleGrade, grade_no):
        db.session.add(VehicleGrade(
            grade_no=grade_no, mdetail_no=mdetail_no, grade_name=grade))
    if not db.session.get(VehicleGradeDetail, gdetail_no):
        db.session.add(VehicleGradeDetail(
            gdetail_no=gdetail_no, grade_no=grade_no, gdetail_name=gdetail))

    return {
        "maker_no": maker_no, "model_no": model_no, "mdetail_no": mdetail_no,
        "grade_no": grade_no, "gdetail_no": gdetail_no,
        "maker": maker, "model": model, "mdetail": mdetail,
        "grade": grade, "gdetail": gdetail,
    }
