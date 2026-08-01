from app.models import GeminiReportCache, Listing
from app.services import gemini_report, i18n_translate
from app.services.i18n_translate import translate
from app.services.llm_hub import LLMError


def _listing(db):
    db.session.add(Listing(car_no="C1", car_name="테스트차", car_year=2020,
                           car_km=30000, imported="수출", sido="서울"))
    db.session.commit()


def test_report_cache_hit(app, db, monkeypatch):
    _listing(db)
    db.session.add(GeminiReportCache(car_no="C1", report_text="캐시된 리포트"))
    db.session.commit()

    def boom(*a, **k):
        raise AssertionError("provider should not be called on cache hit")
    monkeypatch.setattr(gemini_report, "get_provider", boom)

    res = gemini_report.generate_report("C1")
    assert res["ok"] and res["cached"] and res["text"] == "캐시된 리포트"


def test_report_graceful_failure(app, db, monkeypatch):
    _listing(db)

    class FailProvider:
        def generate(self, prompt):
            raise LLMError("quota exceeded")
    monkeypatch.setattr(gemini_report, "get_provider", lambda *a, **k: FailProvider())

    res = gemini_report.generate_report("C1", force=True)
    assert res["ok"] is False
    assert res["error"] == "임시 리포트 생성 불가능"
    assert res["graceful"] is True


def test_translate_passthrough_is_not_cached(app, db):
    # No GEMINI_API_KEY configured in tests → passthrough, and it must NOT be
    # cached, so a later successful translation isn't permanently masked.
    out = translate("사고 없음", "en")
    assert out == "사고 없음"
    from app.models import TranslationCache
    assert TranslationCache.query.filter_by(lang="en").count() == 0


def test_load_pack():
    assert i18n_translate.load_pack("ja")["login"] == "ログイン"
    assert i18n_translate.load_pack("xx")  # falls back to ko


def test_glossary_pairs_reuse_static_ui_dictionary():
    pairs = i18n_translate._glossary_pairs("en")
    assert ("로그인", "Login") in pairs
    pairs_ja = i18n_translate._glossary_pairs("ja")
    assert ("로그인", "ログイン") in pairs_ja


def test_static_lookup_reused_for_known_ui_values(app, db):
    """정적 사전에 있는 값(예: '로그인')은 API 호출 없이 검수된 번역을 그대로 사용."""
    assert translate("로그인", "en") == "Login"
    from app.models import TranslationCache

    assert TranslationCache.query.filter_by(lang="en").count() == 0


def test_vehicle_glossary_translates_maker_model_trim(app, db):
    """제조사·모델·트림은 차량 용어집으로 API 없이 번역된다."""
    assert translate("현대", "en") == "Hyundai"
    assert translate("현대", "ja") == "ヒュンダイ"
    assert translate("그랜저", "en") == "Grandeur"
    assert translate("프레스티지", "ja") == "プレステージ"
    assert translate("현대 그랜저HG 300", "en") == "Hyundai Grandeur HG 300"
    from app.models import TranslationCache

    assert TranslationCache.query.filter_by(lang="en").count() == 0


def test_translate_uses_google_draft_when_configured(app, db, monkeypatch):
    """Google 번역 키만 있으면 초벌 번역을 그대로 사용(Gemini 미설정 시)."""
    monkeypatch.setattr(
        i18n_translate.google_translate, "translate_text",
        lambda text, lang, source_lang="ko": "Google Draft"
    )
    out = translate("프론트펜더 판금 상세", "en")
    assert out == "Google Draft"


def test_translate_polishes_google_draft_with_gemini(app, db, monkeypatch):
    """Google 초벌 + Gemini 윤문 조합 — Gemini가 있으면 다듬은 결과를 사용."""
    monkeypatch.setattr(
        i18n_translate.google_translate, "translate_text",
        lambda text, lang, source_lang="ko": "Google Draft"
    )
    monkeypatch.setattr(i18n_translate, "_call_gemini", lambda text, lang, draft=None: "Polished Result")
    out = translate("프론트펜더 판금 상세", "en")
    assert out == "Polished Result"
