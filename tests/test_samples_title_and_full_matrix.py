"""모수 세부내역 제목 · 전체시세 필터 너비 · 매트릭스 UI."""

from tests.conftest import login


def test_samples_modal_title_can_wrap(client):
    login(client)
    html = client.get("/").get_data(as_text=True)
    start = html.index("bpSamplesModal")
    end = html.index("bpSamplesLoading")
    header = html[start:end]
    assert 'id="bpSamplesSubtitle"' in header
    # 제목이 잘리지 않도록 text-truncate 제거
    assert "text-truncate" not in header
    assert "bp-samples-subtitle" in header or "white-space" in header or "bpSamplesSubtitle" in header


def test_market_js_encodes_sample_title():
    js = open("app/static/js/market.js", encoding="utf-8").read()
    assert "encodeURIComponent" in js
    assert "decodeURIComponent" in js
    assert "sampleTitle" in js or "sample-title" in js


def test_full_market_has_matrix_and_wide_filters(client):
    login(client)
    html = client.get("/market/all").get_data(as_text=True)
    assert 'id="fullMatrix"' in html
    assert 'id="matrixPanel"' in html
    assert "market-full-filters" in html
    assert "매트릭스" in html or "matrix" in html.lower()
    # 검색행이 한 줄에 몰리지 않도록 주 필터에 넉넉한 col
    assert "col-md-3" in html or "col-lg-3" in html or "col-xl-2" in html
