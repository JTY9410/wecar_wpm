from app.services.car_code import build_car_code, extract_grade_gdetail, parse_car_code


def test_build_car_code_is_short_hash():
    code = build_car_code(
        maker="현대", model="쏘나타", mdetail="DN8",
        grade="프리미엄", gdetail="인스퍼레이션",
        car_year=2020, fuel="가솔린", awd="2WD", accident_free=True,
    )
    assert "|" not in code
    assert len(code) == 16
    parsed = parse_car_code(code)
    assert parsed["car_code"] == code


def test_extract_grade_gdetail():
    grade, gdetail = extract_grade_gdetail(
        maker="현대", model="그랜저", mdetail="디 올뉴그랜저 하이브리드",
        car_name="현대 디 올뉴그랜저 하이브리드 1.6 하이브리드 캘리그래피",
    )
    assert grade == "캘리그래피"
    assert "1.6" in gdetail
    assert "현대" not in gdetail
