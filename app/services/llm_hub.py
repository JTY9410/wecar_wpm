"""멀티 LLM 플러그인 스위칭 허브 (PRD §7.1) — Strategy Pattern.

Qualitative only. Never returns/derives numeric price predictions (PRD §2).
Keys resolve: DB override (admin panel) → .env/Config SSOT.
"""
import logging

import requests

from config import Config
from app.extensions import db
from app.models import LLMConfig

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


PROVIDERS = ("gemini", "openai", "claude")

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "claude": "claude-3-5-sonnet-20241022",
}


def _env_key(provider):
    return {
        "gemini": Config.GEMINI_API_KEY,
        "openai": Config.OPENAI_API_KEY,
        "claude": Config.ANTHROPIC_API_KEY,
    }.get(provider, "")


def resolve_api_key(provider):
    """DB 패널 키 우선, 없으면 .env SSOT."""
    row = LLMConfig.query.filter_by(provider=provider).first()
    if row and row.api_key:
        return row.api_key.strip()
    return (_env_key(provider) or "").strip()


def resolve_model(provider):
    row = LLMConfig.query.filter_by(provider=provider).first()
    if row and row.model_name:
        return row.model_name.strip()
    return DEFAULT_MODELS.get(provider, "")


def key_status():
    """Admin UI용 연결 상태 요약 (키 원문은 노출하지 않음)."""
    active = active_provider_name()
    out = []
    for name in PROVIDERS:
        key = resolve_api_key(name)
        row = LLMConfig.query.filter_by(provider=name).first()
        out.append({
            "provider": name,
            "label": {"gemini": "Google Gemini", "openai": "OpenAI ChatGPT",
                      "claude": "Anthropic Claude"}[name],
            "is_active": name == active,
            "model_name": resolve_model(name),
            "key_configured": bool(key),
            "key_source": "panel" if (row and row.api_key) else ("env" if key else "none"),
            "key_hint": (key[:4] + "..." + key[-4:]) if len(key) >= 12 else ("설정됨" if key else "미설정"),
        })
    return out


class BaseProvider:
    name = "base"

    def generate(self, prompt):
        raise NotImplementedError

    def test_connection(self):
        text = self.generate(
            "Reply with exactly: OK. Do not add any other text."
        )
        return bool(text and text.strip())


class GeminiProvider(BaseProvider):
    name = "gemini"

    def generate(self, prompt):
        api_key = resolve_api_key("gemini")
        if not api_key:
            raise LLMError("GEMINI_API_KEY 미설정 - 관리자 LLM 패널 또는 .env에 키를 등록하세요.")
        model = resolve_model("gemini")
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(model=model, contents=prompt)
            text = getattr(resp, "text", None)
            if not text:
                raise LLMError("Gemini 응답이 비어 있습니다.")
            return text
        except LLMError:
            raise
        except ImportError as exc:
            raise LLMError(f"google-genai 미설치: {exc}")
        except Exception as exc:
            logger.exception("Gemini generate failed")
            raise LLMError(f"Gemini 호출 실패: {exc}")


class OpenAIProvider(BaseProvider):
    name = "openai"

    def generate(self, prompt):
        api_key = resolve_api_key("openai")
        if not api_key:
            raise LLMError("OPENAI_API_KEY 미설정 - 관리자 LLM 패널 또는 .env에 키를 등록하세요.")
        model = resolve_model("openai")
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system",
                         "content": "당신은 중고차 도매 시세 정성 분석가입니다. "
                                    "가격 수치를 직접 예측하거나 계산하지 마세요."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.4,
                },
                timeout=Config.API_TIMEOUT,
            )
            if resp.status_code >= 400:
                raise LLMError(f"OpenAI HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except LLMError:
            raise
        except Exception as exc:
            logger.exception("OpenAI generate failed")
            raise LLMError(f"OpenAI 호출 실패: {exc}")


class ClaudeProvider(BaseProvider):
    name = "claude"

    def generate(self, prompt):
        api_key = resolve_api_key("claude")
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY 미설정 - 관리자 LLM 패널 또는 .env에 키를 등록하세요.")
        model = resolve_model("claude")
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 1024,
                    "system": "당신은 중고차 도매 시세 정성 분석가입니다. "
                              "가격 수치를 직접 예측하거나 계산하지 마세요.",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=Config.API_TIMEOUT,
            )
            if resp.status_code >= 400:
                raise LLMError(f"Claude HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            parts = data.get("content") or []
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            if not text:
                raise LLMError("Claude 응답이 비어 있습니다.")
            return text
        except LLMError:
            raise
        except Exception as exc:
            logger.exception("Claude generate failed")
            raise LLMError(f"Claude 호출 실패: {exc}")


_PROVIDERS = {p.name: p for p in (GeminiProvider(), OpenAIProvider(), ClaudeProvider())}


def active_provider_name():
    row = LLMConfig.query.filter_by(is_active=True).first()
    return row.provider if row else "gemini"


def get_provider(name=None):
    name = name or active_provider_name()
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise LLMError(f"알 수 없는 provider: {name}")
    return provider


def set_active(name):
    if name not in _PROVIDERS:
        raise LLMError(f"알 수 없는 provider: {name}")
    for row in LLMConfig.query.all():
        row.is_active = (row.provider == name)
    db.session.commit()


def save_provider_settings(provider, api_key=None, model_name=None, clear_key=False):
    """관리자 패널에서 API 키/모델 저장. api_key=None이면 키 유지, clear_key면 DB키 삭제(.env 폴백)."""
    if provider not in PROVIDERS:
        raise LLMError(f"알 수 없는 provider: {provider}")
    row = LLMConfig.query.filter_by(provider=provider).first()
    if row is None:
        row = LLMConfig(provider=provider, is_active=False,
                        model_name=DEFAULT_MODELS[provider])
        db.session.add(row)
    if clear_key:
        row.api_key = None
    elif api_key is not None and str(api_key).strip():
        row.api_key = str(api_key).strip()
    if model_name is not None and str(model_name).strip():
        row.model_name = str(model_name).strip()
    db.session.commit()
    return row


def test_provider(name=None):
    provider = get_provider(name)
    try:
        provider.test_connection()
        return {"ok": True, "provider": provider.name, "model": resolve_model(provider.name)}
    except LLMError as exc:
        return {"ok": False, "provider": provider.name, "error": str(exc)}


def generate_market_summary(sample_rows):
    """시세 요약 정성 리포트 (가격 수치 예측 금지)."""
    lines = []
    for r in sample_rows[:40]:
        lines.append(
            f"- {r.get('maker','')}/{r.get('model_name','')}/{r.get('car_year','')} "
            f"{r.get('imported','')} {r.get('km_bin','')} "
            f"낙찰평균={r.get('hammer_avg')} 표본={r.get('sample_count')} MoM={r.get('mom_pct')}"
        )
    prompt = (
        "아래는 주간 경매 도매 시세 집계 샘플입니다. "
        "시장 분위기·인기 차종 트렌드·무사고/주행거리 관점의 정성 요약을 한국어로 작성하세요. "
        "새로운 가격을 예측·계산하지 말고, 주어진 숫자만 참고해 서술하세요.\n\n"
        + "\n".join(lines)
    )
    provider = get_provider()
    text = provider.generate(prompt)
    return {"ok": True, "provider": provider.name, "text": text}
