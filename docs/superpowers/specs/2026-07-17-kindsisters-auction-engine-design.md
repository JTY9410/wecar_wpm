# wecarcar1 주간 경매 시세 분석 엔진 — Design Spec

**Date:** 2026-07-17  
**Workspace:** `/Users/USER/dev/car1`  
**Source of truth:** `요구사항.md` + 샘플 엑셀 `20260715_낙찰데이터_최종_최종_최종.xlsx`

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Codebase | **B** — `car1`에 PRD 기준 신규 Flask 앱 구축 (`/Users/USER/dev/car`는 참고만) |
| Scope | **C** — 요구사항 전체(§7 RAG·QLoRA 포함) |
| QLoRA runtime | **A** — 파이프라인·스크립트·스케줄 훅 포함, GPU 없으면 `SKIP` 로그, 학습은 별도 머신 |
| Architecture | **1** — 모놀리식 Flask + SQLite + 단일 Docker Compose |

## 1. Architecture

단일 `web` 컨테이너, SQLite(`instance/wecarcar1_auto.db`), 볼륨 `./instance:/app/instance`.

```
Browser (Bootstrap 5)
    │
    ▼
Flask web (:5000)
  ├─ Auth / RBAC (@login_required, @admin_required)
  ├─ Cascading search + MarketSummary grid
  ├─ Admin: excel upload, sync, retrain, LLM switch, RAG/QLoRA status
  ├─ APScheduler → SYNC_HOURS [9, 13, 18] KST
  └─ services/
       excel_pipeline | sync_engine | price_model | gemini_report
       llm_hub | rag_store | qlora_job | i18n_translate | image_cache
    │
    ▼
SQLite + files under instance/storage/
  {car_images, excel_uploads, chroma, models}
```

**SSOT:** 모든 설정·시드 계정·경로·API는 `.env` → `config.py` Config 싱글톤만. 하드코딩 금지.

**Docker entrypoint:** `flask db upgrade` → admin seed(`INIT_ADMIN_*`) → gunicorn/flask run.

## 2. Database schema

Alembic (`flask db migrate/upgrade`) 필수.

### 2.1 User
- `id`, `username`(unique), `password_hash`, `role` (`USER`|`ADMIN`, default `USER`)
- Seed: `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` (hashed), role=`ADMIN`

### 2.2 Listing (실시간 API 매물 레이크)
- PK `car_no`; `car_name`, `maker_no`, `car_year`, `car_km`, `car_amount_sale`, `sido`, `kind_name`, `imported`, `image_url`, `is_sold`(default False), `updated_at`
- 동기화 응답에 없으면 `is_sold=True`로 표시하되 행은 영구 보존

### 2.3 AuctionRecord (주간 엑셀 원본 — 신규)
엑셀 `경매전체데이터` 1행 ↔ 1레코드:
- `id`, `week_no`, `auction_date`, `maker`, `model_name`, `car_name`, `car_year`, `car_km`, `fuel`, `imported`
- `start_price`, `hope_price`, `hammer_price`, `accident_detail`, `xx_exchange`, `w_panel`
- `is_accident_free`, `car_code`, `km_bin`, `raw_json`, `created_at`

### 2.4 VehiclePriceTable (시세표_테이블 → 카코드 기준)
- `id`, `car_name`, `fuel`, `imported`, `car_year`, `avg_price`
- §5.1 매핑 소스 (trim + Levenshtein ≥ 0.85)

### 2.5 MarketSummary (시세 그리드 집계)
- `car_code`, `car_year`, `imported`, `is_accident_free`, `km_bin`
- `start_avg`, `hammer_avg`, `mom_pct`, `sample_count`, `week_no`, `note`

### 2.6 GeminiReportCache
- PK `car_no` FK→`listing.car_no`, `report_text`, `created_at`

### 2.7 SyncLog
- `sync_type` (`WEEKLY_EXCEL_UPLOAD`|`AUTO_API_SYNC`), `status`, `records_processed`, `error_message`, `created_at`

### 2.8 TranslationCache
- `source_hash`, `source_text`, `lang`, `translated_text`

### 2.9 UploadHistory
- `filename`, `week_no`, `mode` (`append`|`overwrite`|`reset`), `status`, `rows_ok`, `operator`, `created_at`

### 2.10 LLMConfig
- `provider` (`openai`|`gemini`|`claude`), `is_active`, `model_name`

**RAG:** Chroma at `instance/storage/chroma` (DB 테이블 아님). 메타에 `AuctionRecord.id` 참조.

## 3. Data flows

### 3.1 Weekly Excel upload (admin)
1. Dropzone → `EXCEL_UPLOAD_PATH` → `UploadHistory`
2. Load sheet `경매전체데이터`
3. Required columns (실데이터 기준): `경매일`, `제작사`(alias `제조사`), `차명`, `연식`, `주행거리`, `낙찰가`, `내수수출구분`  
   Optional for accident: `사고'A' 상세`, `XX 교환`, `W 판금,용접,꺾임`
4. Clean: non-numeric km → `0`; missing hammer_price → drop row
5. Car-code: match `VehiclePriceTable` (trim) → else Levenshtein ≥ 0.85
6. `km_bin` (15,000km; ≥200,000 → `20만km 이상`); accident-free rule per PRD §5.3
7. Mode: `append` | `overwrite`(delete that `week_no`) | `reset`(clear analysis tables)
8. Persist `AuctionRecord` → rebuild `MarketSummary` (real MoM) → Tier1 `fit()` → RAG embed batch → `SyncLog`

Also ingest `시세표_테이블` (header at row 5) into `VehiclePriceTable` when present in the same workbook.

### 3.2 Listing sync (09/13/18 KST or manual)
1. `KS_API_BASE_URL` + listings path, `timeout=API_TIMEOUT`(120); on failure → `FALLBACK_API_BASE_URL`
2. Upsert `Listing`; missing car_nos → `is_sold=True`
3. Cache `ImageInfo[0].ImageUrl` → `{car_no}_main.jpg`; serve only `/static/storage/car_images/...`
4. Retrain Tier1; write `SyncLog(AUTO_API_SYNC)`

### 3.3 Grid / AI
- Cascading filters → `MarketSummary` grid columns per §6.1
- Tier1: `RandomForestRegressor`, X=`[maker_no|maker, car_year, car_km, imported]`, y=`hammer/sale`; dump `car_price_model.pkl`
- Tier2: on-demand Gemini qualitative text only; cache; `RATE_LIMIT_DAILY=20`; never predict price numbers via Gemini

### 3.4 §7 Self-learning
- RAG: SentenceTransformers `all-MiniLM-L6-v2` → Chroma after upload
- QLoRA: job script + scheduler hook; no GPU → status `SKIP`, web unaffected
- LLM hub: Strategy Pattern switch among OpenAI / Gemini / Claude for admin summary reports

## 4. UI / RBAC / errors

### UI
- Bootstrap 5, `border-radius: 12px`, soft shadow, skeleton loaders
- User: login, cascade search + grid, detail (Tier1 + Gemini button), i18n `ko/en/ja`
- Admin: dashboard, excel upload (dropzone, week, mode radios, history), sync trigger, retrain, LLM panel, RAG/QLoRA status

### RBAC
- USER: no admin DOM (Jinja); `/admin/*` → 403 + toast
- ADMIN: `@admin_required` on all admin APIs

### Graceful fallbacks
| Case | Behavior |
|------|----------|
| KS API failure | Immediate fallback URL |
| Bad/corrupt excel | Reject + toast; DB unchanged |
| Gemini key/quota | Tier1 ok; toast “임시 리포트 생성 불가능” |
| Image download fail | Placeholder; sync still SUCCESS |
| No GPU for QLoRA | `SKIP` log; web ok |

## 5. Config (.env prototype)

```
FLASK_ENV=development
SECRET_KEY=...
KS_API_BASE_URL=https://ks-auto-api.nodeplug.com/kindsisters
FALLBACK_API_BASE_URL=https://extapi.carmanager.co.kr
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPL_API_KEY=
DATABASE_URL=sqlite:///instance/wecarcar1_auto.db
IMAGE_STORAGE_PATH=./instance/storage/car_images
EXCEL_UPLOAD_PATH=./instance/storage/excel_uploads
INIT_ADMIN_USERNAME=wecar
INIT_ADMIN_PASSWORD=1004wecar
```

`config.py` also defines: `RATE_LIMIT_DAILY=20`, `SYNC_HOURS=[9,13,18]`, `API_TIMEOUT=120`, `KM_BUCKET_STEP=15000`, `KM_BUCKET_MAX=200000`, `MODEL_PATH`, `CHROMA_PATH`, `LEVENSHTEIN_THRESHOLD=0.85`.

## 6. Project layout (target)

```
car1/
  .env / .env.example
  config.py
  run.py
  requirements.txt
  Dockerfile / docker-compose.yml / entrypoint.sh
  app/
    __init__.py  extensions.py  models.py  decorators.py
    routes/  (auth, market, listings, admin, api)
    services/ (excel_pipeline, sync_engine, price_model, ...)
    templates/  static/  i18n/{ko,en,ja}.json
  migrations/
  tests/
  scripts/qlora_finetune.py
  instance/   (gitignored runtime)
```

## 7. Verification (PRD §9 — report 3× after implement)

1. SSOT / fallback sync / image local cache / 15k km binning  
2. USER blocked from admin URLs/APIs  
3. Gemini failure → toast; Tier1 offline still works  

## 8. Out of scope / deferred runtime

- Full Llama-3-8B QLoRA training **inside** the Mac/CPU Docker image (script present; execution = SKIP without GPU)
- Real DeepL/AWS Translate calls without API keys (cache table + provider interface; no-op/passthrough when key empty)

## 9. Success criteria

1. Sample xlsx uploads via admin UI and populates `AuctionRecord` + `MarketSummary`
2. Cascade filters show grid with km bins and MoM
3. `docker compose up --build` serves app with seeded `wecar` admin and persisted `instance/` volume
4. Sync fallback and Gemini graceful failure verified in tests/manual checklist
