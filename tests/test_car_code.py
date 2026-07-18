from app.services.car_code import build_car_code, parse_car_code


def test_build_car_code_dimensions():
    code = build_car_code(
        maker="현대", model="쏘나타", mdetail="DN8",
        grade="프리미엄", gdetail="인스퍼레이션",
        car_year=2020, fuel="가솔린", awd="2WD",
    )
    parts = code.split("|")
    assert len(parts) == 8
    assert parts[5] == "2020"
    assert parts[0] == "현대"
    assert "|" in code
    parsed = parse_car_code(code)
    assert parsed["car_year"] == 2020
    assert parsed["awd"] == "2wd"
