# 검증 리포트 (PRD §9 3-Step Verification)

**Date:** 2026-07-17  
**Build:** `docker compose` 단일 `web` 서비스 (SQLite, 볼륨 `./instance:/app/instance`)  
**Test suite:** `pytest` 32 passed

## 실제 데이터 적재 결과 (`20260715_낙찰데이터_최종_최종_최종.xlsx`)

| 항목 | 값 |
|------|----|
| AuctionRecord (원본 레이크) | 2,327 |
| MarketSummary (시세 그리드) | 2,176 |
| VehiclePriceTable (시세표 기준) | 11,117 |
| Tier1 모델 학습 | 성공 (2,327건) |
| 예측 샘플 (2020 현대 수출 5만km) | 약 1,266만원 |

## 1단계 — 요구사항 만족 검증
- **SSOT/무하드코딩:** 모든 설정·경로·시드 계정은 `config.py` + `.env`. `config.SYNC_HOURS==[9,13,18]`, `RATE_LIMIT_DAILY==20` 테스트로 확인.
- **15,000km 구간화:** `test_mileage_bins` — 0/14999/15000/200000/250000 경계 모두 통과. `20만km 이상` 표기 확인.
- **폴백 동기화:** `test_fallback_triggered` — 1차 API 500 → `FALLBACK_API_BASE_URL` 전환. `test_all_fail_raises` — 양쪽 실패 시 `ApiUnavailable`.
- **판매완료 보존:** `test_sync_marks_missing_as_sold` — 응답 누락 매물 `is_sold=True`, 행 영구 보존.
- **이미지 로컬 캐싱:** `image_cache.cache_image` → `{car_no}_main.jpg`, 프론트는 `/static/storage/car_images/...` 가상 경로만. 다운로드 실패 시 placeholder, 동기화는 SUCCESS 유지.
- **무사고 판정:** `test_accident_free` — 교환/판금 0/NaN 또는 '무사고' → 무사고. 골격판금+교환 이력 → 사고차.

## 2단계 — 우회 취약점 차단 검증
- `@admin_required` 데코레이터로 모든 `/admin/*` 보호.
- 로그인 USER가 어드민 API 호출 → **403** (`test_user_blocked_from_admin`, `test_user_cannot_upload`).
- 익명 사용자가 컨테이너 `/admin/sync`, `/admin/upload` 직접 POST → **302 (로그인 리다이렉트)** 로 차단 확인.
- Jinja 템플릿에서 USER에게는 관리자 버튼 미렌더 (`current_user.is_admin` 가드).

## 3단계 — 시스템 예외 복구력 검증
- **Gemini 키/쿼타 실패:** `test_report_graceful_failure` — provider 예외 시 `{"ok":false,"error":"임시 리포트 생성 불가능","graceful":true}` 반환, Tier1 예측은 독립 동작. 프론트 토스트 노출.
- **캐시 재사용:** `test_report_cache_hit` — 캐시 존재 시 외부 호출 없이 반환 (토큰 낭비 방지).
- **번역 API 미설정:** `test_translate_passthrough_and_cache` — DEEPL 키 없을 때 원문 passthrough + 캐시 기록.
- **RAG 미설치:** `test_rag_skips_without_deps` — `sentence-transformers/chromadb` 부재 시 `SKIP`, 웹 정상.
- **QLoRA GPU 부재:** `test_qlora_skip_without_gpu` — GPU 미탐지 시 `SKIP` 로그, 앱 무중단.
- **엑셀 스키마 오류:** `test_missing_column_rejected` — 필수 컬럼 누락 시 `ExcelValidationError`, DB 미변경 + FAIL 로그.

## 컨테이너 배포 확인
```
wecarcar1-web (car1-web) Up (healthy) 0.0.0.0:8090->5000
GET  /health           → {"status":"ok"}
POST /login (wecar)    → 302 (성공)
GET  /api/grid?maker=현대 → 200, 실데이터 반환
flask db upgrade + seed-admin(wecar/ADMIN) 자동 수행
```

호스트 포트는 기존 컨테이너(8080 점유)와 충돌하여 **8090**으로 매핑.
