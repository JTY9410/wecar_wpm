# Admin Analysis Logic Catalog — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an admin Analysis Logic page that documents the wholesale price pipeline and lets admins CRUD/toggle subdivided built-in and custom analysis modules with hybrid runtime wiring.

**Architecture:** `AnalysisLogic` table + `LOGIC_REGISTRY` in `analysis_logic.py`. Pipeline services call `is_active`/`get_params`. Admin UI at `/admin/analysis-logic` (명세 + 로직 tabs). Seed on migrate/app boot does not overwrite existing params/active.

**Tech Stack:** Flask 3.1, SQLAlchemy 2.0, Flask-Migrate, Flask-Login, Flask-WTF CSRF, pytest, Docker Compose `wecarwpm`.

**Spec:** `docs/superpowers/specs/2026-08-11-analysis-logic-design.md`

## Global Constraints

- SQLAlchemy 2.0 only (`select`/`execute`) — no `Model.query`
- Schema via Flask-Migrate only
- Built-in: no hard delete; seed must not overwrite existing `params` / `is_active`
- No formula/`eval` engine; unwired custom codes do not execute
- Match existing admin template/nav patterns; CSRF on POSTs
- Docker: `docker compose -p wecarwpm up -d --build`; push GitHub `main`

## File map

| File | Responsibility |
|------|----------------|
| `app/models.py` | `AnalysisLogic` model |
| `migrations/versions/*_analysis_logic.py` | Alembic |
| `app/services/analysis_logic.py` | Registry, seed, CRUD helpers, param validation |
| `app/services/mileage.py` | Read km step/max from logic params |
| `app/services/excel_pipeline.py` | Skip rebuild if aggregate off |
| `app/services/price_model.py` / admin retrain | Skip if RF off |
| `app/services/hedonic_model.py` | Skip if hedonic off |
| `app/services/weekly_briefing.py` | Thresholds from params; residual gate |
| `app/routes/admin.py` | Analysis-logic routes |
| `app/templates/admin_analysis_logic.html` | UI |
| `app/templates/base.html` | Nav |
| `app/i18n/{ko,en,ja}.json` | `nav_analysis_logic` |
| `app/services/seed.py` or `create_app` | Call `seed_builtin_logics` |
| `tests/test_analysis_logic.py` | Service + wiring tests |
| `README.md` | Short note |

---

### Task 1: Model + migration

**Files:**
- Modify: `app/models.py`
- Create: migration via `flask db migrate -m "analysis_logic"`
- Test: `tests/test_analysis_logic.py` (start)

**Interfaces:**
- Produces: `AnalysisLogic` ORM

- [ ] **Step 1: Failing test**

```python
def test_analysis_logic_persist(db, app):
    from app.models import AnalysisLogic
    with app.app_context():
        row = AnalysisLogic(
            code="mileage.km_bin",
            name="KM구간",
            category="ingest",
            is_builtin=True,
            is_active=True,
            params={"step": 15000, "max": 200000},
            sort_order=10,
        )
        db.session.add(row)
        db.session.commit()
        assert db.session.get(AnalysisLogic, row.id).code == "mileage.km_bin"
```

- [ ] **Step 2: Run — expect fail**

`pytest tests/test_analysis_logic.py::test_analysis_logic_persist -v`

- [ ] **Step 3: Add model** (after `VehicleCodeMapping`)

```python
class AnalysisLogic(db.Model):
    __tablename__ = "analysis_logic"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(32), nullable=False, default="custom", index=True)
    is_builtin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    params = db.Column(db.JSON, nullable=False, default=dict)
    sort_order = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    updated_by = db.Column(db.String(80))
```

- [ ] **Step 4: `flask db migrate` + `upgrade`**
- [ ] **Step 5: Test PASS + commit** — `Add AnalysisLogic model`

---

### Task 2: Service registry + seed + CRUD

**Files:**
- Create: `app/services/analysis_logic.py`
- Modify: `app/services/seed.py` or `app/__init__.py` to call seed after create_all/migrate path
- Test: extend `tests/test_analysis_logic.py`

**Interfaces:**
- Produces:
  - `BUILTIN_SPECS: list[dict]` (code, name, description, category, default_params, sort_order)
  - `seed_builtin_logics() -> int`  # created count
  - `is_active(code: str) -> bool`
  - `get_params(code: str, defaults: dict | None = None) -> dict`
  - `list_logics(category: str | None = None) -> list[AnalysisLogic]`
  - `upsert(*, code, name, description, category, params, is_active, is_builtin=False, updated_by=None) -> AnalysisLogic`
  - `set_active(logic_id: int, active: bool) -> AnalysisLogic | None`
  - `delete_logic(logic_id: int) -> tuple[bool, str]`  # False if builtin
  - `validate_params(code: str, params: dict) -> dict`  # raises ValueError

Built-in defaults (exact):

| code | default_params |
|------|----------------|
| `mileage.km_bin` | `{"step": 15000, "max": 200000}` |
| `aggregate.market_summary` | `{}` |
| `predict.random_forest` | `{}` |
| `predict.hedonic` | `{}` |
| `briefing.price_alert` | `{"threshold_pct": 5.0, "min_samples": 2}` |
| `briefing.surge_alert` | `{"threshold_pct": 30.0}` |
| `briefing.hedonic_residual` | `{"threshold_pct": 15.0}` |

Seed: insert if code missing; if exists, update name/description/sort only — **never** overwrite `params` or `is_active`.

`is_active`: missing row → `True` (safe default for builtins).  
`get_params`: merge DB params over defaults; missing row → defaults.

- [ ] **Step 1: Tests** — seed creates 7; second seed created=0 and params preserved; delete_logic builtin fails; upsert custom + delete ok; validate_params rejects threshold 200
- [ ] **Step 2: Implement service**
- [ ] **Step 3: PASS + commit** — `Add analysis_logic registry seed and CRUD`

---

### Task 3: Wire pipeline (hybrid runtime)

**Files:**
- Modify: `app/services/mileage.py`
- Modify: `app/services/excel_pipeline.py` (`rebuild_market_summary`)
- Modify: `app/services/price_model.py` and/or `app/routes/admin.py` retrain/upload train calls
- Modify: `app/services/hedonic_model.py` and briefing residual path
- Modify: `app/services/weekly_briefing.py`
- Test: `tests/test_analysis_logic.py` + existing briefing/excel tests if needed

**Interfaces:**
- Consumes: `is_active`, `get_params`

Wiring rules:

1. `calculate_mileage_bin`:  
   `p = get_params("mileage.km_bin", {"step": Config.KM_BUCKET_STEP, "max": Config.KM_BUCKET_MAX})`  
   use `p["step"]`, `p["max"]` when caller did not pass explicit step/cap.

2. `rebuild_market_summary`: if `not is_active("aggregate.market_summary")`: return early (0 rows / no-op) and log.

3. `PriceModel.train` / predict entry: if RF inactive → train no-op return False; predict returns None or clear error payload (match existing API shape).

4. Hedonic train/predict/briefing residual: gate on `predict.hedonic` / `briefing.hedonic_residual`.

5. Briefing alerts: read thresholds from `get_params` instead of module constants (keep constants as defaults).

- [ ] **Step 1: Failing tests**

```python
def test_price_alert_threshold_from_db(db, app):
    # seed, set briefing.price_alert threshold_pct=99, build tiny fixture weeks
    # assert no price_flag when move is 10%
    ...

def test_aggregate_off_skips_rebuild(db, app):
    # deactivate aggregate.market_summary; call rebuild; MarketSummary count unchanged or rebuild returns skipped
    ...
```

- [ ] **Step 2: Implement wiring**
- [ ] **Step 3: PASS + commit** — `Wire analysis_logic into mileage aggregate predict briefing`

---

### Task 4: Admin UI + routes + nav

**Files:**
- Modify: `app/routes/admin.py`
- Create: `app/templates/admin_analysis_logic.html`
- Modify: `app/templates/base.html`
- Modify: `app/i18n/ko.json`, `en.json`, `ja.json`
- Test: `tests/test_admin.py` or `tests/test_analysis_logic.py`

**Routes:**
- `GET /admin/analysis-logic` → template `?tab=docs|logics`
- `POST /admin/analysis-logic/toggle/<id>`
- `POST /admin/analysis-logic/save` (form or JSON fields: code, name, description, category, params JSON, is_active)
- `POST /admin/analysis-logic/delete/<id>`
- `POST /admin/analysis-logic/seed`

Docs tab: numbered pipeline steps (엑셀→AuctionRecord→km_bin→MarketSummary→RF→Hedonic→Briefing) with code badges.

Logics tab: table + toggle + edit form + add custom + seed button. Builtin delete disabled. Note: “커스텀은 레지스트리 미연결 시 실행되지 않음”.

- [ ] **Step 1: `test_analysis_logic_page_requires_admin`**
- [ ] **Step 2: Implement**
- [ ] **Step 3: PASS + commit** — `Add admin analysis logic page`

---

### Task 5: README + full audit + Docker + GitHub

**Files:** `README.md` (short Analysis Logic section)

- [ ] **Step 1:** `python3 -m pytest -q` — fix failures only
- [ ] **Step 2:** `flask db upgrade` in Docker via entrypoint (already runs migrate); ensure seed called from `create_app` or entrypoint after upgrade
- [ ] **Step 3:** Smoke — no `Model.query`; `/admin/analysis-logic` 200 as admin; `/healthz` 200
- [ ] **Step 4:** `docker compose -p wecarwpm up -d --build` → Healthy; uid 10001
- [ ] **Step 5:** Commit + `git push origin HEAD`

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| AnalysisLogic model + migrate | 1 |
| Registry seed CRUD validation | 2 |
| Hybrid runtime wiring | 3 |
| Admin page docs+logics + nav | 4 |
| pytest / Docker / GitHub | 5 |
| No eval / no unwired custom exec | honored |

## Self-review notes

- Param keys: `threshold_pct`, `min_samples`, `step`, `max` — consistent across tasks
- Builtin codes exactly as spec table
- Seed never overwrites params/is_active
