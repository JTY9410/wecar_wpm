# wecarcar1 Auction Engine — Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax. Execute task-by-task; each task ends with a runnable verification.

**Goal:** Build a Flask app in `car1` that ingests the weekly auction Excel, stores it in SQLite (Alembic-managed), computes market summaries, serves a cascading-filter price grid with a local RandomForest price predictor and on-demand Gemini qualitative reports, syncs live listings with fallback + local image cache, and ships via a single Docker Compose service.

**Architecture:** Monolithic Flask + SQLite + APScheduler, all config from `.env`→`config.py`. RAG via Chroma; QLoRA script SKIPs without GPU.

**Tech Stack:** Python 3.11, Flask 3, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, pandas, openpyxl, scikit-learn, APScheduler, google-genai, sentence-transformers, chromadb, python-Levenshtein, gunicorn.

## Global Constraints
- SSOT: no hardcoded settings/paths/keys — read from `config.Config` only.
- DB path fixed: `instance/wecarcar1_auto.db`.
- Docker volume `./instance:/app/instance`.
- Gemini = qualitative only; never predicts price numbers.
- Admin seed from `INIT_ADMIN_USERNAME`/`INIT_ADMIN_PASSWORD` (hashed).
- `SYNC_HOURS=[9,13,18]`, `API_TIMEOUT=120`, `RATE_LIMIT_DAILY=20`, `KM_BUCKET_STEP=15000`, `KM_BUCKET_MAX=200000`.

---

### Task 1: Project scaffold + config + extensions
**Files:** `requirements.txt`, `.env`, `.env.example`, `.gitignore`, `.dockerignore`, `config.py`, `run.py`, `app/__init__.py`, `app/extensions.py`, `tests/conftest.py`, `tests/test_config.py`
- [ ] Config singleton reads `.env`; app factory `create_app`; `/health` route returns `{"status":"ok"}`.
- [ ] Test: app factory boots, `/health` returns 200, Config has SYNC_HOURS==[9,13,18].
- Verify: `pytest tests/test_config.py -v`

### Task 2: Models + migrations + admin seed
**Files:** `app/models.py`, `migrations/*`, `app/services/seed.py`, `tests/test_models.py`
- [ ] All 10 models per spec §2. `flask db migrate/upgrade`. Seed admin idempotently.
- [ ] Test: create tables, seed twice → one `wecar` ADMIN user, password verifies.
- Verify: `pytest tests/test_models.py -v`

### Task 3: Excel pipeline (binning, accident, car-code, summary)
**Files:** `app/services/excel_pipeline.py`, `app/services/mileage.py`, `app/services/car_code.py`, `tests/test_excel_pipeline.py`, `tests/fixtures/mini.xlsx`
- [ ] `calculate_mileage_bin`, accident-free rule, Levenshtein car-code map, schema validation, modes append/overwrite/reset, build `AuctionRecord` + `MarketSummary` with real MoM.
- [ ] Ingest `시세표_테이블` (header row 5) → `VehiclePriceTable`.
- [ ] Tests: bin edge cases (0, 14999, 15000, 200000), accident logic, missing-hammer drop, overwrite replaces week.
- Verify: `pytest tests/test_excel_pipeline.py -v`

### Task 4: Auth + RBAC
**Files:** `app/routes/auth.py`, `app/decorators.py`, `app/templates/login.html`, `tests/test_rbac.py`
- [ ] Flask-Login; `@admin_required`; USER→`/admin/*` returns 403.
- [ ] Tests: login ok/bad, USER blocked from admin API, ADMIN allowed.
- Verify: `pytest tests/test_rbac.py -v`

### Task 5: Market grid + cascading filter API
**Files:** `app/routes/market.py`, `app/services/market_query.py`, `app/templates/market.html`, `tests/test_market.py`
- [ ] Cascade endpoints (makers→models→details→years), grid query over `MarketSummary`.
- [ ] Tests: filter narrows results; grid returns km_bin + mom_pct fields.
- Verify: `pytest tests/test_market.py -v`

### Task 6: Tier1 price model
**Files:** `app/services/price_model.py`, `tests/test_price_model.py`
- [ ] RandomForest train/dump/load/predict on AuctionRecord; label-encode categoricals.
- [ ] Tests: train on fixture, predict returns numeric, missing model handled.
- Verify: `pytest tests/test_price_model.py -v`

### Task 7: Sync engine + fallback + image cache
**Files:** `app/services/api_client.py`, `app/services/sync_engine.py`, `app/services/image_cache.py`, `tests/test_sync.py`
- [ ] KS→fallback on error; upsert Listing; missing→is_sold; image to local path; SyncLog.
- [ ] Tests (mocked HTTP): fallback triggers on 500/timeout; is_sold flip; image path served via /static route only.
- Verify: `pytest tests/test_sync.py -v`

### Task 8: Gemini report + LLM hub + rate limit
**Files:** `app/services/llm_hub.py`, `app/services/gemini_report.py`, `app/routes/api.py`, `tests/test_gemini.py`
- [ ] Strategy pattern (openai/gemini/claude); cache; daily limit 20; graceful failure returns toast flag; never numeric price.
- [ ] Tests (mocked): cache hit skips call; quota/exception → graceful error payload.
- Verify: `pytest tests/test_gemini.py -v`

### Task 9: RAG + QLoRA hook + i18n
**Files:** `app/services/rag_store.py`, `scripts/qlora_finetune.py`, `app/services/i18n_translate.py`, `app/i18n/{ko,en,ja}.json`, `tests/test_rag_i18n.py`
- [ ] Chroma embed after upload (lazy import, skip if lib missing); QLoRA `run()` returns SKIP without GPU; translate passthrough + cache when no key.
- [ ] Tests: translate cache; qlora SKIP path; rag guarded when unavailable.
- Verify: `pytest tests/test_rag_i18n.py -v`

### Task 10: Admin UI + scheduler + upload/sync/retrain routes
**Files:** `app/routes/admin.py`, `app/services/scheduler.py`, `app/templates/admin_*.html`, `app/templates/base.html`, `app/static/css/app.css`, `tests/test_admin.py`
- [ ] Dropzone upload, mode radios, history table, manual sync/retrain, LLM toggle, RAG/QLoRA status; APScheduler at SYNC_HOURS guarded by `ENABLE_SCHEDULER`.
- [ ] Tests: upload endpoint processes fixture; admin-only.
- Verify: `pytest tests/test_admin.py -v`

### Task 11: Dockerize
**Files:** `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`
- [ ] Single `web` service, volume `./instance:/app/instance`, entrypoint runs `flask db upgrade`+seed, gunicorn.
- [ ] Verify: `docker compose build` then `up`; `/health` 200; upload sample xlsx works; data persists across restart.

### Task 12: Full verification (PRD §9 ×3) + real Excel run
**Files:** `tests/test_e2e.py`, `docs/superpowers/verification-report.md`
- [ ] Load real `20260715_...xlsx`, run pipeline, assert AuctionRecord/MarketSummary counts>0; run 3-step checklist; write report.
- Verify: `pytest -q` all green.

## Self-Review
- Spec coverage: §2 models→T2; §4 excel→T3; §5 pipeline/sync/image/AI→T3,6,7,8; §6 UI/RBAC→T4,5,10; §7→T9,10; §8 script→T3; §9→T12. All covered.
- No placeholders; each task has verify command.
