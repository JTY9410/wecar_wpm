# Admin Analysis Logic Catalog (기준시세 산정·분석 로직)

**Date:** 2026-08-11  
**Status:** Approved (brainstorming)  
**Repo:** car1 / wecar WPM (`wecar_wpm`)

## Problem

Wholesale price calculation (낙찰 집계·km bin·RF/헤도닉·주간 브리핑 알림) lives only as code constants. Admins cannot review, enable/disable, or edit subdivided logic items from the UI.

## Goals

- Admin page **분석로직** (`/admin/analysis-logic`) with:
  - **명세** tab: document current base-price (낙찰) pipeline steps
  - **로직** tab: CRUD + activate/deactivate per logic item
- Seed built-in logics matching the current pipeline; allow custom logics (stored; executed only if registry-wired)
- Hybrid runtime: safe params (thresholds, km bin) apply immediately; core modules (aggregate/RF/hedonic) honor on/off
- Migration, full pytest, Docker rebuild, GitHub push

## Non-goals

- Arbitrary formula/`eval` engine
- Changing car2 retail base-price logic
- Executing unwired custom codes at runtime

## Locked decisions

| Topic | Choice |
|-------|--------|
| Unit | Module catalog + documentation tab |
| Runtime | Hybrid (params live; core on/off) |
| Add | Built-in subdivided items + custom rows |
| Approach | `AnalysisLogic` DB + code `LOGIC_REGISTRY` |

## Architecture

```
Admin /admin/analysis-logic
  ├── Tab: 명세 (pipeline docs ↔ logic codes)
  └── Tab: 로직 (CRUD / toggle)

Pipeline services
  → analysis_logic.is_active(code) / get_params(code, defaults)
  → skip or apply
```

## Data model: `AnalysisLogic`

| Column | Notes |
|--------|--------|
| id | PK |
| code | unique, `^[a-z][a-z0-9_.]{1,63}$` |
| name, description | display |
| category | ingest \| aggregate \| predict \| briefing \| custom |
| is_builtin | bool |
| is_active | bool |
| params | JSON object |
| sort_order | int |
| updated_at, updated_by | audit |

CRUD rules:
- Built-in: edit name/description/params/active; **no hard delete** (toggle off)
- Custom: hard delete allowed
- Seed upserts missing built-ins; **does not overwrite** existing `params` / `is_active`

## Built-in registry (v1)

| code | Immediate effect |
|------|------------------|
| `mileage.km_bin` | params `step`, `max` |
| `aggregate.market_summary` | on/off — OFF skips `rebuild_market_summary` |
| `predict.random_forest` | on/off — train/predict skip or safe error |
| `predict.hedonic` | on/off |
| `briefing.price_alert` | `threshold_pct`, `min_samples` |
| `briefing.surge_alert` | `threshold_pct` |
| `briefing.hedonic_residual` | `threshold_pct` |

Custom `category=custom` rows are documentation/reservation until a future registry hook exists.

## Service API

`app/services/analysis_logic.py`:
- `seed_builtin_logics()`, `get_logic`, `is_active`, `get_params`, `list_logics`, `upsert`, `set_active`, `delete`

Wire into: `mileage.py`, `excel_pipeline.rebuild_market_summary`, `price_model` / admin retrain, `hedonic_model`, `weekly_briefing`.

## Admin routes

- `GET /admin/analysis-logic`
- `POST /admin/analysis-logic/toggle/<id>`
- `POST /admin/analysis-logic/save`
- `POST /admin/analysis-logic/delete/<id>`
- `POST /admin/analysis-logic/seed`

All: `@login_required` + `@admin_required` + CSRF on POST.

Nav: side rail + mobile **분석로직**.

## Validation

Per-code param schemas (numeric ranges). Invalid payload → 400, no save.

## Testing success criteria

- Seed creates built-ins; toggle/save/delete (custom) work
- Changing `briefing.price_alert` params affects next briefing build
- RF/hedonic OFF skips train/predict safely
- Full pytest green; migrate upgrades; Docker Healthy; pushed to GitHub

## Risks

- Turning off `aggregate.market_summary` leaves MarketSummary stale until re-enabled + rebuild
- Custom logics without registry hooks never run (by design — document in UI)

## Out of scope follow-ups

- Formula DSL
- Version history / audit log table
- A/B multiple active profiles per code
