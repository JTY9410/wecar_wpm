from app.services.accident import is_accident_free
from app.services.mileage import calculate_mileage_bin


def test_mileage_bins():
    assert calculate_mileage_bin(0) == "0만~1.5만km"
    assert calculate_mileage_bin(14999) == "0만~1.5만km"
    assert calculate_mileage_bin(15000) == "1.5만~3만km"
    assert calculate_mileage_bin(200000) == "20만km 이상"
    assert calculate_mileage_bin(250000) == "20만km 이상"
    assert calculate_mileage_bin("미상") == "미상"
    assert calculate_mileage_bin(None) == "미상"


def test_accident_free():
    assert is_accident_free("무사고", 0, 0) is True
    assert is_accident_free("단순교환", 0, 0) is True   # exchange/panel zero → free
    assert is_accident_free("골격판금", "프론트펜더(좌)", 0) is False
    assert is_accident_free(None, None, None) is True
