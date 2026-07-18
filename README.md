# wecar WPM (wecarcar1)

경매 도매 시세 분석 시스템. `wecar PM`(car)과 독립 운영하며, 도매 시세 External API로 소매 연동을 지원합니다.

## 실행

```bash
docker compose up -d --build
# http://localhost:8090
```

관리자: `.env`의 `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` (기본 `wecar` / `1004wecar`)

## 카코드

`제조사|모델|상세모델|등급|상세등급|년식|유종|AWD`

## Wholesale API (car 연동)

- `GET /api/v1/wholesale/health`
- `GET /api/v1/wholesale/prices` — Header `X-API-Key`
- `GET /api/v1/wholesale/lookup`

키: `.env`의 `EXTERNAL_API_KEY`
