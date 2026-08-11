# Admin API Keys, Spec & Vehicle Code Mapping (car1 ↔ car2)

**Date:** 2026-08-11  
**Status:** Approved (brainstorming)  
**Repo:** car1 / wecar WPM (`wecar_wpm`)

## Problem

1. Partner wholesale API exists (`/api/v1/wholesale/*`) but there is no in-app API spec and only a single env `EXTERNAL_API_KEY` (no admin UI, no multi-key lifecycle).
2. car1 and car2 (copy at `/Users/USER/dev/car2 복사본`) both use 5-level vehicle codes, but IDs can diverge. Callers need either side’s codes to resolve.
3. Admin nav label “API 키” points at LLM settings; sync routes and codes/cascade APIs overlap and confuse operators.
4. Changes must ship via Docker + GitHub after verification.

## Goals

- Admin **Developer hub** with API documentation, multi API-key issue/revoke, and code-mapping management.
- **Bidirectional code compatibility**: car1 or car2 codes (and names) resolve to car1 internal codes for wholesale/lookup.
- Hybrid mapping fill: car2 sync candidates + manual/CSV confirm; fuzzy name match as runtime fallback.
- UX cleanup for admin developer entry; document codes vs cascade; dedupe sync trigger.
- Full regression check (`pytest`, Docker health) and push to GitHub.

## Non-goals

- Merging car1 and car2 codebases or databases.
- Requiring car2 code changes in the same PR (car2 remains a codes source + API consumer).
- OpenAPI/Swagger binary or external portal.
- Deleting `/api/cascade` or `/api/codes` (document roles only).

## Locked decisions

| Topic | Choice |
|-------|--------|
| Approach | car1 single hub |
| Mapping | Bidirectional resolve on car1 |
| API keys | Multi-key DB + env legacy fallback |
| Mapping fill | Hybrid sync + manual/CSV + fuzzy |
| UX | Developer section consolidates docs/keys/mapping |

## Architecture

```
Admin /admin/developer
  ├── Tab: API 명세서 (HTML)
  ├── Tab: API 키 (ApiKey CRUD)
  └── Tab: 코드 매핑 (VehicleCodeMapping + sync/CSV)

Request (wholesale / codes)
  → require_api_key (DB hash | EXTERNAL_API_KEY)
  → resolve_vehicle_codes(...)
  → MarketSummary / vehicle_* queries
```

Config:

- `CAR2_CODES_BASE_URL` (default `http://host.docker.internal:8080`) for candidate sync.
- Keep `EXTERNAL_API_KEY` as fallback when no active DB key matches.

## Data model

### ApiKey

| Column | Notes |
|--------|--------|
| id | PK |
| name | Operator memo |
| key_prefix | First 8 chars for list UI |
| key_hash | Werkzeug scrypt/hash only |
| is_active | bool |
| created_at / revoked_at / last_used_at | timestamps |
| created_by | optional user id/username |

Plaintext shown once at create: `wpm_` + secrets token.

### VehicleCodeMapping

| Column | Notes |
|--------|--------|
| id | PK |
| level | maker \| model \| mdetail \| grade \| gdetail |
| car2_code / car1_code | codes |
| car2_name / car1_name | display/audit |
| status | candidate \| confirmed \| rejected |
| match_score | float nullable |
| source | sync \| csv \| manual \| fuzzy |
| updated_at | |

Uniqueness: prefer unique on `(level, car2_code)` and soft-guard confirmed `(level, car1_code)`. Confirmed/rejected rows are not overwritten by sync.

Migration via Flask-Migrate only.

## API key auth

1. Read `X-API-Key` or `Authorization: Bearer`.
2. Match active `ApiKey` by verifying hash; bump `last_used_at`.
3. Else constant-time compare to `EXTERNAL_API_KEY`.
4. 401 invalid; 503 if no keys configured (no active DB keys and empty env).

Admin routes (session + `@admin_required`): list/create/revoke under `/admin/developer/keys`.

## API specification tab

In-app HTML documenting:

- Public: `GET /api/v1/wholesale/health`
- Keyed: `/prices`, `/lookup`, `/codes/makers`, `/codes/models`, plus new `/codes/modeldetails|grades|gradedetails`
- Note: session APIs (`/api/codes`, `/api/cascade`, …) login-required; clarify cascade = MarketSummary names, codes = vehicle_* hierarchy.

Include headers, query params, sample JSON, and “car1 or car2 codes accepted” for resolve-enabled endpoints.

## Code resolve & sync

### resolve_vehicle_codes (SSOT service)

Priority:

1. Input already car1 PK → use as-is.
2. Confirmed `VehicleCodeMapping` car2→car1.
3. Name normalize + fuzzy (port car2 alias/paren-strip patterns) against car1 masters.
4. Partial result + `match_level` / `unresolved` if incomplete.

Wholesale responses should include car1 codes and mapped car2 aliases when known.

Apply at: wholesale `prices`, `lookup`, `codes/*` query params; optionally `/api/codes` entry.

### Sync

Admin action “Sync from car2”:

1. Fetch makers → models → modeldetails → grades → gradedetails from car2 `/api/codes/*`.
2. Upsert `candidate` rows by name match; skip overwrite of confirmed/rejected.
3. If car2 unreachable, show error; CSV still works.

CSV columns: `level,car2_code,car1_code,car2_name,car1_name`.

### Wholesale parity

Add grade-level code list endpoints to mirror car2 tree depth.

## UX cleanup

- Sidebar: “개발자” → `/admin/developer` (replace misleading LLM “API 키” anchor).
- Dashboard: keep LLM/translate as “AI 설정”; remove duplicate AI-learning CTA if sidebar already covers it.
- Unify `/admin/sync` and `/admin/sync/trigger` (redirect one to the other).
- Mobile admin nav: add Developer link.
- Do not remove cascade/codes routes.

## Error audit & deploy

- Run full `pytest`; add tests for keys, resolve, mapping CSV/confirm, wholesale auth.
- Fix real bugs found (no drive-by refactors).
- `docker compose -p wecarwpm up -d --build`; verify Healthy, non-root app process, `/healthz`.
- Commit and push to GitHub `main`.

## Testing success criteria

- Issue key → wholesale 200; revoke → 401; env fallback still works.
- car2 code on prices/lookup resolves via confirmed mapping or fuzzy to car1 data.
- Developer page renders; CSRF-safe POSTs.
- No regression on existing suite.

## Risks

- car2 offline → sync unavailable (CSV/manual mitigate).
- Name collisions → candidates need human confirm before wholesale relies on mapping.
- Hash-only API keys → lost plaintext cannot be recovered (re-issue only).

## Out of scope follow-ups

- Push mapping package into car2 repo.
- Rate limiting / per-key quotas.
- Full OpenAPI export.
