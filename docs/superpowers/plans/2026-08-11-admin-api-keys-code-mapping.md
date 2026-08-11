# Admin API Keys, Spec & Vehicle Code Mapping — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an admin Developer hub with multi API-key lifecycle, in-app wholesale API docs, and bidirectional car1↔car2 vehicle-code resolve, then Docker rebuild + GitHub push.

**Architecture:** car1-only hub at `/admin/developer`. `ApiKey` + `VehicleCodeMapping` tables; wholesale auth checks DB hashes then env fallback; `resolve_vehicle_codes()` normalizes any car1/car2 code/name before MarketSummary queries; car2 HTTP sync creates mapping candidates only.

**Tech Stack:** Flask 3.1, SQLAlchemy 2.0, Flask-Migrate, Flask-Login, Flask-WTF CSRF, Werkzeug scrypt, pytest, Docker Compose (`wecarwpm`).

**Spec:** `docs/superpowers/specs/2026-08-11-admin-api-keys-code-mapping-design.md`

## Global Constraints

- SQLAlchemy 2.0 only: `select()` / `session.execute` — no `Model.query`.
- Schema changes only via Flask-Migrate.
- Secrets never logged; API key plaintext shown once at create; store hash only.
- Keep `EXTERNAL_API_KEY` env as legacy fallback.
- Do not merge car1/car2 repos; do not delete `/api/cascade` or `/api/codes`.
- Match existing admin template/CSS patterns; CSRF on state-changing POSTs.
- Docker project: `wecarwpm`, port 8090; GitHub repo `wecar_wpm`.

## File map

| File | Responsibility |
|------|----------------|
| `app/models.py` | `ApiKey`, `VehicleCodeMapping` |
| `migrations/versions/*_api_keys_code_mapping.py` | Alembic revision |
| `config.py`, `.env.example` | `CAR2_CODES_BASE_URL` |
| `app/services/api_keys.py` | issue / verify / revoke keys |
| `app/services/code_resolve.py` | normalize + resolve car1/car2 codes |
| `app/services/code_mapping_sync.py` | fetch car2 codes → candidates; CSV |
| `app/routes/wholesale.py` | multi-key auth; resolve; extra code endpoints |
| `app/routes/admin.py` | `/developer` + key/mapping actions |
| `app/templates/admin_developer.html` | tabs: docs / keys / mapping |
| `app/templates/base.html`, `admin_dashboard.html` | nav + AI 설정 label |
| `app/i18n/ko.json` (en/ja if keys exist) | `nav_developer` |
| `tests/test_api_keys.py`, `tests/test_code_resolve.py`, `tests/test_wholesale.py` | coverage |
| `README.md` | wholesale + developer hub notes |

---

### Task 1: Models + migration + config

**Files:**
- Modify: `app/models.py` (append after `AiLearningMilestone`)
- Modify: `config.py`, `.env.example`
- Create: migration via `flask db migrate`
- Test: `tests/test_models.py` (extend)

**Interfaces:**
- Produces: `ApiKey`, `VehicleCodeMapping` ORM classes; `Config.CAR2_CODES_BASE_URL: str`

- [ ] **Step 1: Write failing model assertions**

Add to `tests/test_models.py`:

```python
def test_api_key_and_mapping_tables(db):
    from app.models import ApiKey, VehicleCodeMapping
    from werkzeug.security import generate_password_hash

    k = ApiKey(
        name="test",
        key_prefix="wpm_test",
        key_hash=generate_password_hash("wpm_secret", method="scrypt"),
        is_active=True,
    )
    m = VehicleCodeMapping(
        level="maker",
        car2_code="c2_mk_1",
        car1_code="mk_hyundai",
        car2_name="현대",
        car1_name="현대",
        status="confirmed",
        source="manual",
        match_score=1.0,
    )
    db.session.add_all([k, m])
    db.session.commit()
    assert db.session.get(ApiKey, k.id).key_prefix == "wpm_test"
    assert db.session.get(VehicleCodeMapping, m.id).level == "maker"
```

- [ ] **Step 2: Run test — expect ImportError / table missing**

Run: `pytest tests/test_models.py::test_api_key_and_mapping_tables -v`

- [ ] **Step 3: Add models**

Append to `app/models.py`:

```python
class ApiKey(db.Model):
    __tablename__ = "api_key"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    key_prefix = db.Column(db.String(16), nullable=False, index=True)
    key_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    revoked_at = db.Column(db.DateTime)
    last_used_at = db.Column(db.DateTime)
    created_by = db.Column(db.String(80))


class VehicleCodeMapping(db.Model):
    __tablename__ = "vehicle_code_mapping"
    __table_args__ = (
        db.UniqueConstraint("level", "car2_code", name="uq_vcm_level_car2"),
    )

    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(16), nullable=False, index=True)
    car2_code = db.Column(db.String(64), nullable=False)
    car1_code = db.Column(db.String(64), nullable=False)
    car2_name = db.Column(db.String(256))
    car1_name = db.Column(db.String(256))
    status = db.Column(db.String(16), nullable=False, default="candidate", index=True)
    match_score = db.Column(db.Float)
    source = db.Column(db.String(16), nullable=False, default="manual")
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
```

Add to `config.py`:

```python
CAR2_CODES_BASE_URL = os.getenv("CAR2_CODES_BASE_URL", "http://host.docker.internal:8080")
```

Add to `.env.example`:

```text
CAR2_CODES_BASE_URL=http://host.docker.internal:8080
```

- [ ] **Step 4: Migrate**

```bash
export FLASK_APP=run.py
flask db migrate -m "api_key and vehicle_code_mapping"
flask db upgrade
```

- [ ] **Step 5: Re-run test — PASS**

Run: `pytest tests/test_models.py::test_api_key_and_mapping_tables -v`

- [ ] **Step 6: Commit**

```bash
git add app/models.py config.py .env.example migrations/versions tests/test_models.py
git commit -m "Add ApiKey and VehicleCodeMapping models"
```

---

### Task 2: API key service + wholesale auth

**Files:**
- Create: `app/services/api_keys.py`
- Modify: `app/routes/wholesale.py` (`require_api_key`)
- Create: `tests/test_api_keys.py`

**Interfaces:**
- Consumes: `ApiKey`, `Config.EXTERNAL_API_KEY`
- Produces:
  - `issue_api_key(name: str, created_by: str | None) -> tuple[ApiKey, str]`  # plaintext once
  - `verify_api_key(provided: str) -> ApiKey | Literal["env"] | None`
  - `revoke_api_key(key_id: int) -> bool`
  - `has_any_auth_configured() -> bool`

- [ ] **Step 1: Failing tests**

```python
# tests/test_api_keys.py
from app.services import api_keys

def test_issue_and_verify(db, app):
    with app.app_context():
        row, plain = api_keys.issue_api_key("partner", created_by="wecar")
        assert plain.startswith("wpm_")
        assert api_keys.verify_api_key(plain) is not None
        assert api_keys.verify_api_key("wrong") is None

def test_revoke_rejects(db, app):
    with app.app_context():
        row, plain = api_keys.issue_api_key("x", created_by="wecar")
        assert api_keys.revoke_api_key(row.id) is True
        assert api_keys.verify_api_key(plain) is None

def test_env_fallback(client, app):
    app.config["EXTERNAL_API_KEY"] = "env-legacy-key"
    r = client.get("/api/v1/wholesale/codes/makers", headers={"X-API-Key": "env-legacy-key"})
    assert r.status_code == 200
```

- [ ] **Step 2: Run — FAIL (module missing)**

Run: `pytest tests/test_api_keys.py -v`

- [ ] **Step 3: Implement `app/services/api_keys.py`**

```python
from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timezone

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import ApiKey


def _utcnow():
    return datetime.now(timezone.utc)


def issue_api_key(name: str, created_by: str | None = None) -> tuple[ApiKey, str]:
    plain = "wpm_" + secrets.token_hex(24)
    row = ApiKey(
        name=(name or "unnamed").strip()[:120],
        key_prefix=plain[:12],
        key_hash=generate_password_hash(plain, method="scrypt"),
        is_active=True,
        created_by=(created_by or "")[:80] or None,
    )
    db.session.add(row)
    db.session.commit()
    return row, plain


def has_any_auth_configured() -> bool:
    env = (current_app.config.get("EXTERNAL_API_KEY") or "").strip()
    if env:
        return True
    n = db.session.scalar(
        db.select(db.func.count()).select_from(ApiKey).where(ApiKey.is_active.is_(True))
    )
    return bool(n)


def verify_api_key(provided: str) -> ApiKey | str | None:
    provided = (provided or "").strip()
    if not provided:
        return None
    rows = db.session.execute(
        db.select(ApiKey).where(ApiKey.is_active.is_(True))
    ).scalars().all()
    for row in rows:
        if check_password_hash(row.key_hash, provided):
            row.last_used_at = _utcnow()
            db.session.commit()
            return row
    expected = (current_app.config.get("EXTERNAL_API_KEY") or "").strip()
    if expected and hmac.compare_digest(provided, expected):
        return "env"
    return None


def revoke_api_key(key_id: int) -> bool:
    row = db.session.get(ApiKey, key_id)
    if not row or not row.is_active:
        return False
    row.is_active = False
    row.revoked_at = _utcnow()
    db.session.commit()
    return True
```

- [ ] **Step 4: Replace `require_api_key` in `wholesale.py`**

```python
from app.services import api_keys as api_key_service

def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not api_key_service.has_any_auth_configured():
            return jsonify({"ok": False, "error": "API key not configured"}), 503
        provided = request.headers.get("X-API-Key", "")
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
        if api_key_service.verify_api_key(provided) is None:
            return jsonify({"ok": False, "error": "invalid api key"}), 401
        return fn(*args, **kwargs)
    return wrapper
```

- [ ] **Step 5: Tests PASS**

Run: `pytest tests/test_api_keys.py -v`

- [ ] **Step 6: Commit**

```bash
git add app/services/api_keys.py app/routes/wholesale.py tests/test_api_keys.py
git commit -m "Add multi API-key issue/verify with env fallback"
```

---

### Task 3: Code resolve service

**Files:**
- Create: `app/services/code_resolve.py`
- Create: `tests/test_code_resolve.py`

**Interfaces:**
- Consumes: `VehicleCodeMapping`, `VehicleMaker`…`VehicleGradeDetail`
- Produces:
  - `normalize_label(value: str | None) -> str`
  - `resolve_vehicle_codes(*, maker_no=None, model_no=None, mdetail_no=None, grade_no=None, gdetail_no=None, maker=None, model=None, mdetail=None, grade=None, gdetail=None) -> dict`
  - Return shape: `{maker_no, model_no, mdetail_no, grade_no, gdetail_no, maker_name, model_name, mdetail_name, grade_name, gdetail_name, car2: {…}, match_level: str, unresolved: list[str]}`

Resolve order per level: car1 PK exists → confirmed mapping by car2_code → name fuzzy against car1 master.

- [ ] **Step 1: Failing tests**

```python
def test_resolve_car1_passthrough(db, app):
    from app.models import VehicleMaker
    from app.services.code_resolve import resolve_vehicle_codes
    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_h", maker_name="현대"))
        db.session.commit()
        out = resolve_vehicle_codes(maker_no="mk_h")
        assert out["maker_no"] == "mk_h"
        assert out["match_level"] == "maker"

def test_resolve_car2_via_mapping(db, app):
    from app.models import VehicleMaker, VehicleCodeMapping
    from app.services.code_resolve import resolve_vehicle_codes
    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_h", maker_name="현대"))
        db.session.add(VehicleCodeMapping(
            level="maker", car2_code="C2MAKER", car1_code="mk_h",
            status="confirmed", source="manual", car2_name="현대", car1_name="현대",
        ))
        db.session.commit()
        out = resolve_vehicle_codes(maker_no="C2MAKER")
        assert out["maker_no"] == "mk_h"
        assert out["car2"]["maker_no"] == "C2MAKER"

def test_resolve_by_name_alias(db, app):
    from app.models import VehicleMaker
    from app.services.code_resolve import resolve_vehicle_codes
    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_kia", maker_name="기아"))
        db.session.commit()
        out = resolve_vehicle_codes(maker="기아자동차")
        assert out["maker_no"] == "mk_kia"
```

- [ ] **Step 2: Run — FAIL**

Run: `pytest tests/test_code_resolve.py -v`

- [ ] **Step 3: Implement `code_resolve.py`**

Port alias map and `normalize_label` from car2 `code_mapping.py` (paren strip, FWD/AWD strip, maker aliases). Implement `_map_code(level, code)`, `_match_name(level, name, parent_car1_code)`, and `resolve_vehicle_codes` walking maker→gdetail.

Keep file ≤ ~250 lines; no DB writes in resolve (read-only). Fuzzy: exact normalized name first, then token Jaccard ≥ 0.85, else unresolved.

- [ ] **Step 4: Tests PASS**

Run: `pytest tests/test_code_resolve.py -v`

- [ ] **Step 5: Commit**

```bash
git add app/services/code_resolve.py tests/test_code_resolve.py
git commit -m "Add bidirectional vehicle code resolve"
```

---

### Task 4: Wire resolve into wholesale + extend codes tree

**Files:**
- Modify: `app/routes/wholesale.py`
- Create: `tests/test_wholesale.py`

**Interfaces:**
- Consumes: `resolve_vehicle_codes`, existing MarketSummary queries
- Produces: endpoints `/codes/modeldetails`, `/codes/grades`, `/codes/gradedetails`; prices/lookup accept car2 `*_no`

- [ ] **Step 1: Failing wholesale tests**

```python
def test_wholesale_prices_resolves_mapped_maker(client, db, app):
    from app.models import MarketSummary, VehicleMaker, VehicleCodeMapping
    app.config["EXTERNAL_API_KEY"] = "k"
    with app.app_context():
        db.session.add(VehicleMaker(maker_no="mk_h", maker_name="현대"))
        db.session.add(VehicleCodeMapping(
            level="maker", car2_code="C2H", car1_code="mk_h",
            status="confirmed", source="manual",
        ))
        db.session.add(MarketSummary(
            car_code="x", maker="현대", model_name="쏘나타", mdetail_name="DN8",
            grade_name="프리미엄", gdetail_name="-", car_year=2020, fuel="가솔린",
            awd="2WD", imported="국산", is_accident_free=True, km_bin="0-1.5만",
            hammer_avg=1500, sample_count=3,
        ))
        db.session.commit()
    r = client.get("/api/v1/wholesale/prices?maker_no=C2H", headers={"X-API-Key": "k"})
    assert r.status_code == 200
    assert r.get_json()["count"] >= 1

def test_codes_grades_endpoint(client, app):
    app.config["EXTERNAL_API_KEY"] = "k"
    r = client.get("/api/v1/wholesale/codes/grades", headers={"X-API-Key": "k"})
    assert r.status_code == 200
    assert "items" in r.get_json()
```

Adjust `MarketSummary` required columns to match model (inspect `app/models.py` before writing fixture).

- [ ] **Step 2: Run — FAIL (maker_no ignored / grades 404)**

Run: `pytest tests/test_wholesale.py -v`

- [ ] **Step 3: Update wholesale**

In `prices` and `lookup`:
1. Collect `maker_no`…`gdetail_no` and name args.
2. Call `resolve_vehicle_codes(...)`.
3. Filter MarketSummary by resolved **names** (existing columns) and/or car1 hierarchy if present.
4. Include in JSON: `resolved` object with car1 codes + `car2` aliases.

Add routes:

```python
@wholesale_bp.route("/codes/modeldetails")
@require_api_key
def codes_modeldetails():
    model_no = request.args.get("model_no")
    resolved = resolve_vehicle_codes(model_no=model_no) if model_no else {}
    q = db.select(VehicleModelDetail)
    if resolved.get("model_no"):
        q = q.where(VehicleModelDetail.model_no == resolved["model_no"])
    ...
```

Same pattern for grades (`mdetail_no`) and gradedetails (`grade_no`). For makers/models list responses, optionally attach `car2_code` from confirmed mappings.

- [ ] **Step 4: Tests PASS**

Run: `pytest tests/test_wholesale.py tests/test_api_keys.py -v`

- [ ] **Step 5: Commit**

```bash
git add app/routes/wholesale.py tests/test_wholesale.py
git commit -m "Resolve car2 codes in wholesale and extend code tree API"
```

---

### Task 5: Mapping sync + CSV service

**Files:**
- Create: `app/services/code_mapping_sync.py`
- Create: `tests/test_code_mapping_sync.py`

**Interfaces:**
- Produces:
  - `sync_candidates_from_car2(base_url: str | None = None) -> dict`  # `{ok, created, skipped, error}`
  - `import_csv(text: str) -> dict`  # upsert confirmed/candidate from CSV
  - `export_csv() -> str`
  - `set_mapping_status(mapping_id: int, status: str) -> bool`

Sync: GET `{base}/api/codes/makers` then nested models…; for each item name-match car1; if no row for `(level, car2_code)` insert `candidate`; if existing status in `confirmed|rejected` skip.

Use `urllib.request` or `requests` if already in requirements; timeout 15s. Mock HTTP in tests with `unittest.mock.patch`.

CSV header: `level,car2_code,car1_code,car2_name,car1_name` — import sets `status=confirmed`, `source=csv`.

- [ ] **Step 1: Failing tests** (mock car2 JSON makers list → one candidate)
- [ ] **Step 2: Implement sync/CSV**
- [ ] **Step 3: Tests PASS**
- [ ] **Step 4: Commit** — `git commit -m "Add car2 code mapping sync and CSV import"`

---

### Task 6: Admin developer hub UI + routes

**Files:**
- Modify: `app/routes/admin.py`
- Create: `app/templates/admin_developer.html`
- Modify: `app/templates/base.html`, `app/templates/admin_dashboard.html`
- Modify: `app/i18n/ko.json` (+ en/ja keys if present)

**Interfaces:**
- Routes:
  - `GET /admin/developer` → template with tabs `docs|keys|mapping` (`?tab=`)
  - `POST /admin/developer/keys` — issue (flash plaintext once via session flash or response)
  - `POST /admin/developer/keys/<id>/revoke`
  - `POST /admin/developer/mapping/sync`
  - `POST /admin/developer/mapping/<id>/status` — body `status=confirmed|rejected`
  - `POST /admin/developer/mapping/manual` — create confirmed row
  - `POST /admin/developer/mapping/import` — CSV file
  - `GET /admin/developer/mapping/export` — CSV download
- All mutating routes: `@admin_required` + CSRF (form `csrf_token`)

- [ ] **Step 1: Failing admin access test**

```python
def test_developer_requires_admin(client):
    r = client.get("/admin/developer")
    assert r.status_code in (302, 401)
    login(client)
    r = client.get("/admin/developer")
    assert r.status_code == 200
    assert b"API" in r.data or "명세서".encode() in r.data
```

- [ ] **Step 2: Implement routes + template**

Template: Bootstrap 5 tabs already used in admin. Docs tab: static HTML tables for wholesale endpoints (from spec). Keys tab: table + create form; show plaintext in alert only after create. Mapping tab: filters, sync button, status buttons, CSV upload, manual form.

Docs content must mention:
- car1/car2 codes accepted on prices/lookup
- `/api/codes` = vehicle_* hierarchy (login)
- `/api/cascade` = MarketSummary name cascade (login)

- [ ] **Step 3: Nav cleanup**

In `base.html`: replace LLM “API 키” side-rail item with Developer → `admin.developer`. Add mobile link for admin. Keep “AI” side item pointing to `#llm-settings` with title “AI 설정” OR remove AI rail item and leave AI settings only on dashboard — prefer: **Developer** new item + rename AI title to “AI 설정”.

In `admin_dashboard.html`: heading “AI 설정”; remove duplicate AI-learning big CTA if sidebar has 학습.

Unify sync: keep one handler; leave both route decorators (already identical) — add comment OR make `/sync/trigger` redirect. Prefer keep dual decorator (already unified).

- [ ] **Step 4: Tests + commit**

```bash
pytest tests/test_admin.py tests/test_api_keys.py -v
git commit -m "Add admin developer hub for API docs, keys, and mapping"
```

---

### Task 7: README + full audit + Docker + GitHub

**Files:**
- Modify: `README.md` (Wholesale + Developer hub section)
- Fix any bugs found in audit (only real failures)

- [ ] **Step 1: Full pytest**

Run: `python3 -m pytest -q`  
Expected: all pass (fix failures before proceeding).

- [ ] **Step 2: Smoke audit checklist**
  - No new `Model.query` / `db.session.query` under `app/`
  - `/admin/developer` 200 as admin
  - Issue key → wholesale health/codes 200
  - Revoke → 401
  - Broken template links none for developer nav

- [ ] **Step 3: Docker**

```bash
docker compose -p wecarwpm up -d --build
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8090/healthz
docker exec wecarwpm-web cat /proc/1/status | head -8   # uid 10001
```

- [ ] **Step 4: Commit remaining + push**

```bash
git add -A
git status
git commit -m "Document developer hub and ship API key / code mapping"
git push origin HEAD
```

---

## Spec coverage check

| Spec requirement | Task |
|------------------|------|
| ApiKey + VehicleCodeMapping | 1 |
| Multi-key + env fallback | 2 |
| resolve_vehicle_codes bidirectional | 3 |
| wholesale prices/lookup + full codes tree | 4 |
| Sync candidates + CSV | 5 |
| Developer hub UI + nav UX | 6 |
| pytest / Docker / GitHub | 7 |
| Document codes vs cascade | 6 (docs tab) |
| Non-goal: no cascade delete | honored |
| Non-goal: no car2 repo change | honored |

## Placeholder / consistency scan

- Function names stable: `issue_api_key`, `verify_api_key`, `revoke_api_key`, `resolve_vehicle_codes`, `sync_candidates_from_car2`.
- Key prefix format `wpm_` + hex throughout Tasks 2–6.
- Mapping statuses: `candidate|confirmed|rejected` only.
