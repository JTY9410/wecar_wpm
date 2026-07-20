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

## Wholesale API (car2 연동 — 추후)

car2에서 `WPM_INTEGRATION_ENABLED=1` 로 활성화 후 사용:

- `GET /api/v1/wholesale/health`
- `GET /api/v1/wholesale/prices` — Header `X-API-Key`
- `GET /api/v1/wholesale/lookup`

키: `.env`의 `EXTERNAL_API_KEY`
