from app.services.accident import classify_accident, is_accident_free
from app.services.mileage import calculate_mileage_bin


def test_mileage_bins_10k(app):
    with app.app_context():
        assert calculate_mileage_bin(0) == "0만~1만km"
        assert calculate_mileage_bin(9999) == "0만~1만km"
        assert calculate_mileage_bin(10000) == "1만~2만km"
        assert calculate_mileage_bin(15000) == "1만~2만km"
        assert calculate_mileage_bin(200000) == "20만km 이상"
        assert calculate_mileage_bin(250000) == "20만km 이상"
        assert calculate_mileage_bin("미상") == "미상"
        assert calculate_mileage_bin(None) == "미상"


def test_classify_accident_grades():
    assert classify_accident("무사고", 0, 0) == ("무사고", True)
    assert classify_accident("단순교환", 0, 0) == ("단순교환", False)
    assert classify_accident("골격판금", "프론트펜더(좌)", 0) == ("골격판금", False)
    assert classify_accident("사고", 0, "도어(좌)") == ("외판판금", False)
    assert classify_accident("사고", "본넷", 0) == ("외판교환", False)
    assert classify_accident(None, None, None) == ("무사고", True)


def test_accident_free():
    assert is_accident_free("무사고", 0, 0) is True
    assert is_accident_free("단순교환", 0, 0) is False
    assert is_accident_free("골격판금", "프론트펜더(좌)", 0) is False
    assert is_accident_free(None, None, None) is True
