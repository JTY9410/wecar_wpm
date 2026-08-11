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

## Developer hub (관리자)

관리자 로그인 후 사이드바 **개발자** (`/admin/developer`)에서 다음을 처리합니다.

| 탭 | 내용 |
|----|------|
| **docs** | Wholesale API 엔드포인트·인증·car1/car2 코드 체계 설명 |
| **keys** | API 키 발급(`wpm_` + hex)·폐기 — 평문 키는 발급 직후 1회만 표시 |
| **mapping** | car1↔car2 `VehicleCodeMapping` 동기화·확정/거절·수동 등록·CSV 가져오기/내보내기 |

매핑 상태: `candidate` · `confirmed` · `rejected` (car2 레코드 cascade 삭제는 하지 않음).

## 분석로직 (관리자)

사이드바 **분석로직** (`/admin/analysis-logic`)에서 도매 시세(낙찰) 산정·분석 모듈을 관리합니다.

| 탭 | 내용 |
|----|------|
| **파이프라인** | 엑셀→집계→RF/헤도닉→브리핑 단계 명세와 연결 `code` |
| **로직 관리** | 내장/커스텀 항목 활성·파라미터 수정·추가·삭제(내장은 비활성만) |

런타임: km구간·브리핑 임계값은 DB params 즉시 반영. 집계/RF/헤도닉은 on/off. 레지스트리 미연결 커스텀은 저장만 되며 실행되지 않습니다.

## Wholesale API 인증 (다중 키)

car2 등 외부 소비자용 REST (`/api/v1/wholesale/*`).

**인증:** `X-API-Key: <key>` 또는 `Authorization: Bearer <key>`

1. **DB 발급 키** — Developer hub에서 발급·`verify_api_key`로 검증  
2. **환경 변수 폴백** — `.env`의 `EXTERNAL_API_KEY` (레거시 단일 키, DB 키와 병행 가능)

폐기된 키·잘못된 키 → `401`. `/health`는 인증 없음.

### 엔드포인트

| Method | Path | 인증 |
|--------|------|------|
| GET | `/api/v1/wholesale/health` | 없음 |
| GET | `/api/v1/wholesale/prices` | 키 |
| GET | `/api/v1/wholesale/lookup` | 키 |
| GET | `/api/v1/wholesale/codes/makers` | 키 |
| GET | `/api/v1/wholesale/codes/models?maker_no=` | 키 |
| GET | `/api/v1/wholesale/codes/modeldetails?model_no=` | 키 |
| GET | `/api/v1/wholesale/codes/grades?mdetail_no=` | 키 |
| GET | `/api/v1/wholesale/codes/gradedetails?grade_no=` | 키 |

`prices` / `lookup`는 WPM 내부 번호(`maker_no`, `model_no`, …) 또는 car2 코드로 `resolve_vehicle_codes` 양방향 해석 후 필터합니다. codes 트리 응답의 `car2_code`는 **confirmed** 매핑이 있을 때만 포함됩니다.

## car2 코드 연동 (`CAR2_CODES_BASE_URL`)

car1(WPM)과 car2(PM) DB·저장소는 분리되어 있습니다. car2 쪽 코드 트리를 읽어 매핑 후보를 만들 때 car2 HTTP 베이스 URL이 필요합니다.

```bash
# .env — Docker에서 호스트의 car2(:8080) 접근 예
CAR2_CODES_BASE_URL=http://host.docker.internal:8080
```

로컬 단독 실행 시 car2가 없으면 동기화는 실패할 수 있으며, WPM 도매 기능 자체는 SQLite만으로 동작합니다.

## 로컬 개발 / 테스트

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
flask db upgrade   # 또는 migrate
python3 -m pytest -q
```

Docker 프로젝트명 예: `docker compose -p wecarwpm up -d --build` → `http://127.0.0.1:8090/healthz`
