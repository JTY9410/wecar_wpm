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


def test_translate_passthrough_and_cache(app, db):
    # No DEEPL key → passthrough, but cached row still created.
    out = translate("사고 없음", "en")
    assert out == "사고 없음"
    from app.models import TranslationCache
    assert TranslationCache.query.filter_by(lang="en").count() == 1


def test_load_pack():
    assert i18n_translate.load_pack("ja")["login"] == "ログイン"
    assert i18n_translate.load_pack("xx")  # falls back to ko
