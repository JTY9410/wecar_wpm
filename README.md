# wecar WPM (wecarcar1)

경매 도매 시세 분석 시스템. **wecar PM(car2)** 과 독립 운영하며, 도매 시세 External API로 추후 소매 연동을 지원합니다.

## 독립 운영 구성

| 항목 | car1 (WPM) | car2 (PM) |
|------|------------|-----------|
| 서비스 ID | `wecarcar1` | `wecarcar2` |
| 웹 포트 | **8090** | **8080** |
| DB | SQLite `instance/wecarcar1_auto.db` | PostgreSQL `wecarcar2_auto` |
| Docker 네트워크 | `wecarwpm_net` (독립) | `wecarcar2_net` (독립) |
| GitHub | [wecar_wpm](https://github.com/JTY9410/wecar_wpm) | [wecar_pm](https://github.com/JTY9410/wecar_pm) |

## 실행

```bash
docker compose up -d --build
# http://localhost:8090
```

관리자: `.env`의 `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` (기본 `wecar` / `1004wecar`)

## 카코드

`제조사|모델|상세모델|등급|상세등급|년식|유종|AWD`

## 다국어 (ko/en/ja)

- 상단바 언어 스위처(KO/EN/JA)로 전환, 화면 레이아웃(사이드 레일·모바일 네비·버튼)은 언어별 자동 조정된다.
- 고정 UI 문구: `app/i18n/{ko,en,ja}.json` (사람이 검수한 번역, 정적 사전). `|tr` 필터가 원문 값이 정적 사전에 있으면
  이 검수된 번역을 그대로 재사용한다.
- 차명·제조사·모델명·사고내역 등 자유 텍스트: `app/services/i18n_translate.py` 가 두 엔진을 조합해 번역 후 `TranslationCache`에 캐시.
  1) **Google Cloud Translation API** — 관리자 대시보드(`/admin`)에서 API 키 등록 시 1차 초벌 번역(넓은 커버리지).
     키는 기존 `LLMConfig` 테이블(provider=`google_translate`)에 저장되어 별도 마이그레이션이 필요 없다.
  2) **Gemini**(`GEMINI_API_KEY`) — Google 초벌 결과를 용어집·과거 캐시를 참고해 자연스럽게 다듬는다(윤문).
  Google 키가 없으면 Gemini가 직접 번역, 둘 다 없으면 원문 그대로 표시(그레이스풀 패스스루).

## Wholesale API (car2 연동 — 추후)

car2에서 `WPM_INTEGRATION_ENABLED=1` 로 활성화 후 사용:

- `GET /api/v1/wholesale/health`
- `GET /api/v1/wholesale/prices` — Header `X-API-Key`
- `GET /api/v1/wholesale/lookup`

키: `.env`의 `EXTERNAL_API_KEY`
