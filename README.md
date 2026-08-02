# wecar WPM — 도매시세분석 (wecarcar1)

**도매시세분석** 전용 시스템(경매 낙찰가 그리드·매트릭스·주간 브리핑·엑셀 업로드/내보내기).  
**소매시세분석(car2 / wecar PM)과 코드를 합치지 않으며**, DB·Docker·GitHub 모두 독립 운영합니다.  
소매 매물·기준가는 car2(`:8080`)가 담당합니다.

## 독립 운영 구성

| 항목 | car1 (도매시세분석 / WPM) | car2 (소매시세분석 / PM) |
|------|---------------------------|--------------------------|
| 서비스 ID | `wecarcar1` | `wecarpm` |
| 웹 포트 | **8090** | **8080** |
| DB | SQLite `instance/wecarcar1_auto.db` | PostgreSQL `wecarpm_auto` |
| Docker 네트워크 | `wecarwpm_net` (독립) | `wecarpm_net` (독립) |
| GitHub | [wecar_wpm](https://github.com/JTY9410/wecar_wpm) | [wecar_pm](https://github.com/JTY9410/wecar_pm) |

## 실행

```bash
docker compose up -d --build
# http://localhost:8090
```

관리자: `.env`의 `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` (기본 `wecar` / `1004wecar`)

## 주요 기능

- 도매 시세 그리드 / 연식×주행 매트릭스 / 모수 세부내역
- 시세 Excel 내보내기 (`/api/export/grid`)
- 주간 WoW 브리핑 (`/briefing`)
- AI 예상가격 분석, Admin AI학습진행도
- 주간 경매 엑셀 업로드 → `auction_record` / `market_summary`

## 카코드

`제조사|모델|상세모델|등급|상세등급|년식|유종|AWD`

## 다국어 (ko/en/ja)

- 상단바 언어 스위처(KO/EN/JA)
- 고정 UI: `app/i18n/{ko,en,ja}.json`
- 자유 텍스트: Google Translate + Gemini 윤문 + `TranslationCache` / `LearnedGlossary`

## Wholesale API (소매 car2 선택 연동)

car2에서 필요 시:

- `GET /api/v1/wholesale/health`
- `GET /api/v1/wholesale/prices` — Header `X-API-Key`
- `GET /api/v1/wholesale/lookup`

키: `.env`의 `EXTERNAL_API_KEY`
