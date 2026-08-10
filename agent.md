# Agent Constitution — Rules of Engagement (2026)

> Cursor AI 에이전트가 기술 스택·개발 원칙·하이브리드 UX·품질 기준을 일관 준수하기 위한 최상위 헌법(SSOT).  
> 루트 `agent.md`가 원본이며, `.cursorrules`는 본 문서의 강제 요약이다.

**Last reviewed:** 2026-08-09  
**UI reference:** [Quicken Web Progress — Mobbin](https://mobbin.com/screens/05b1b240-bf8c-4939-889a-01fb0b80fab2)  
(Side Nav · Multi-Column · Card · Grid/List · Progress)

---

## 1. Tech Stack (Pinned Floors)

프로덕션은 **안정 최신**만 사용. 알파/베타(예: Bootstrap 6 alpha)는 금지.

| Layer | Spec (2026) | Notes |
|-------|-------------|--------|
| Runtime | **Python 3.12+** (권장 **3.12.x**; 로컬은 3.13 가능) | Flask 3.1 최소 3.9 — 프로젝트 표준은 3.12+ |
| Web | **Flask ≥3.1.3,<3.2** | Application Factory (`create_app`) 필수 |
| ORM | **SQLAlchemy ≥2.0.36,<2.1** + **Flask-SQLAlchemy ≥3.1.1,<3.2** | **2.0 스타일만** (`select()`, `session.execute`) |
| Migrate | **Flask-Migrate ≥4.1,<5** (Alembic) | 수동 SQL 스키마 변경 금지 |
| Auth helpers | **Flask-Login** + **Werkzeug** password hash (scrypt 우선) | 평문 비밀번호 금지 |
| Forms/CSRF | **Flask-WTF ≥1.2** | 상태 변경 POST에 CSRF |
| Config | **python-dotenv** | `.env` → `config.py` |
| Prod WSGI | **Gunicorn ≥23** | Compose `web` 서비스 |
| Frontend | HTML5 / CSS3 / **Vanilla ES2023+** | 번들러 없이 시작; 필요 시 최소 Vite |
| UI kit | **Bootstrap 5.3.8** (CDN 또는 vendor pin) | Bootstrap 6은 아직 alpha → 채택 금지 |
| Icons | Bootstrap Icons 1.11+ 또는 SVG 스프라이트 | 이모지 UI 금지 |
| Lint/Test | **Ruff** + **pytest ≥8** | CI에서 필수 권장 |
| Container | Docker **multi-stage** + Compose v2 | base: `python:3.12-slim-bookworm` |
| DB (dev) | SQLite | 파일 경로·마이그레이션 SSOT |
| DB (prod option) | PostgreSQL 16+ | `DATABASE_URL`로 전환 가능하게 `config` 설계 |

### requirements 핀 예시

```text
Flask>=3.1.3,<3.2
SQLAlchemy>=2.0.36,<2.1
Flask-SQLAlchemy>=3.1.1,<3.2
Flask-Migrate>=4.1,<5
Flask-Login>=0.6.3,<0.7
Flask-WTF>=1.2,<2
python-dotenv>=1.0,<2
gunicorn>=23,<25
Werkzeug>=3.1,<4
```

---

## 2. Core Principles

### A. SSOT

- 비즈니스 로직·모델·설정은 **한 곳만**. 복사 금지.
- 시크릿·환경: `.env` (커밋 금지). 예: `SECRET_KEY`, `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.
- 앱 설정: `config.py`만. 코드에 매직넘버/키 하드코딩 금지.
- Flask: `create_app()` + Blueprint. 전역 `app` 남용 금지.

### B. DB — Migrate only + SQLAlchemy 2.0

```text
1) apps/models.py 수정 (Mapped[] / mapped_column)
2) flask db migrate -m "..."
3) flask db upgrade
```

- 레거시 `Model.query` / `db.session.query(...)` 신규 코드 금지.
- 권장: `db.session.execute(db.select(User).filter_by(...)).scalar_one_or_none()`.

### C. UI Flow 주석 (템플릿 필수)

```html
<!--
  [UI Flow]
  1. Auth / entry
  2. Data: METHOD /path → shape
  3. States: loading | empty | error | success
  4. Actions → next view
-->
```

### D. 3-Step Iteration

제안 전 **검토 → 수정 → 검증**을 최소 3회. pytest·브라우저 스모크·Sub-agent 활용.

### E. Security baseline (2026)

- CSRF on mutating forms; `SECRET_KEY` from env.
- Password: `generate_password_hash(..., method="scrypt")` (또는 werkzeug 기본 최신).
- HTTPS 가정 헤더(프록시): `ProxyFix` when behind reverse proxy.
- 템플릿 출력 이스케이프 유지; `|safe`는 최소화·근거 주석.
- `.env`·시드 비밀번호를 클라이언트 JS/로그에 넣지 말 것.

---

## 3. Hybrid App & PWA (Modern)

### A. PWA

강제 설치 불가 → 표준 유도만.

- `static/manifest.json`: `name`, `short_name`, `start_url`, `id`, `display: "standalone"`, `display_override`, `icons` (192/512, `purpose: "any maskable"`), `theme_color` / `background_color`, optional `shortcuts` / `screenshots`.
- `static/service-worker.js`: 버전드 캐시; HTML network-first, 정적 asset cache-first. 구 SW는 `skipWaiting`+`clients.claim` 신중히.
- `beforeinstallprompt` → 커스텀 설치 카드(첫 방문/체류 시). iOS는 “홈 화면에 추가” 가이드 UI.
- `base.html`: `<link rel="manifest">`, apple-touch-icon, theme-color meta.

### B. In-app browser escape

감지: `KAKAOTALK`, `NAVER`, `Instagram`, `FBAN`/`FBAV` 등 (`static/js/app.js`).

| Platform | Strategy |
|----------|----------|
| Android | `intent://…#Intent;scheme=https;package=com.android.chrome;end` (또는 기본 브라우저) |
| iOS | 탈출 안내 오버레이 + 링크 복사 + Safari에서 열기 가이드 |

로그인·PWA 설치 플로우는 **시스템 브라우저**에서 이어지도록 UX 설계.

---

## 4. UI/CSS Standard (Trend + Mobbin)

Reference: [Mobbin Quicken Progress](https://mobbin.com/screens/05b1b240-bf8c-4939-889a-01fb0b80fab2)

### Layout patterns (필수)

| Pattern | Rule |
|---------|------|
| Side Navigation | Desktop 고정/접이; 활성 상태 명확 |
| Multi-Column | Nav + Main (+ optional aside) |
| Card / Grid List | 콘텐츠 단위는 카드·그리드 |
| Progress | 대시보드 핵심 진행 UI |
| Mobile | Drawer 또는 bottom nav로 축소 |
| Motion | 2–3개 의도적 트랜지션만 (과한 애니메이션 금지) |

### Visual (2026 CSS)

- **Design tokens** in `:root` + `[data-theme="dark"]` (또는 `color-scheme` / `light-dark()`).
- Glass: `backdrop-filter` + 반투명 surface; **보라 네온/과한 glow AI 슬롭 금지**.
- Prefer **oklch()** / `color-mix()` for accents; system UI fonts 스택 + 한글(`Pretendard` 또는 `Apple SD Gothic Neo` 등) 명시.
- Use **container queries** for card grids where useful; clamp() for fluid type.
- Bootstrap 5.3: `data-bs-theme="light|dark"` 와 커스텀 CSS 변수 정렬.
- a11y: focus-visible, 대비 WCAG 2.2 AA, `prefers-reduced-motion` 존중.

```css
:root {
  color-scheme: light dark;
  --bg: oklch(0.97 0.01 240);
  --surface: color-mix(in oklch, white 72%, transparent);
  --text: oklch(0.25 0.02 250);
  --muted: oklch(0.48 0.02 250);
  --accent: oklch(0.48 0.12 160);
  --border: color-mix(in oklch, var(--text) 10%, transparent);
  --radius: 12px;
  --blur: 16px;
  --font: "Pretendard", "Apple SD Gothic Neo", system-ui, sans-serif;
}
[data-theme="dark"] {
  --bg: oklch(0.22 0.02 250);
  --surface: color-mix(in oklch, oklch(0.30 0.02 250) 80%, transparent);
  --text: oklch(0.95 0.01 240);
  --muted: oklch(0.72 0.02 240);
  --accent: oklch(0.72 0.12 160);
}
.glass {
  background: var(--surface);
  backdrop-filter: blur(var(--blur));
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
```

---

## 5. Directory Structure

```text
project-root/
├── agent.md
├── .cursorrules
├── .env.example              # 커밋 가능 샘플 (실비밀 없음)
├── .env                      # gitignore
├── config.py                 # SSOT Config
├── app.py                    # create_app 진입
├── wsgi.py                   # gunicorn wsgi:app
├── requirements.txt          # 핀된 의존성
├── pyproject.toml            # optional: ruff/pytest config
├── Dockerfile                # multi-stage, non-root USER
├── docker-compose.yml
├── apps/
│   ├── __init__.py           # factory + extensions
│   ├── models.py
│   ├── routes.py
│   └── auth.py               # optional blueprint
├── migrations/
├── static/
│   ├── js/
│   │   ├── app.js            # UA escape, theme, install UX
│   │   └── sw-register.js
│   ├── css/
│   │   └── style.css
│   ├── icons/                # PWA icons
│   ├── manifest.json
│   └── service-worker.js
├── templates/
│   ├── base.html
│   ├── login.html
│   └── index.html
└── tests/
    └── ...
```

---

## 6. Default Admin Seed

| Field | Default (dev only) |
|-------|--------------------|
| Username | `wecar` |
| Password | `1004wecar` |

- Override: `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env`.
- Seed **한 곳**만 (CLI `flask seed-admin` 권장).
- Hash only; never commit real prod passwords.
- First login: force password change 권장(프로덕션).

---

## 7. Docker (modern defaults)

- Stage 1: deps build; Stage 2: runtime `python:3.12-slim-bookworm`.
- Non-root user; `gunicorn -b 0.0.0.0:8000 "wsgi:app"`.
- Compose: `web` + volume for SQLite(dev) or `db` service(prod Postgres).
- Healthcheck: `GET /healthz` (경량 라우트 필수).

---

## 8. Agent Mandatory Checklist

1. **Versions** — 위 핀 준수; Bootstrap 6 alpha / 구식 Flask 2.x 도입 금지.
2. **SSOT** — 설정은 `.env` + `config.py`만.
3. **DB** — models → migrate → upgrade; SQLAlchemy **2.0 API**.
4. **Templates** — `[UI Flow]` 주석; Bootstrap 5.3 + Mobbin Quicken 레이아웃.
5. **Hybrid** — PWA manifest/SW/install UX + 인앱 탈출.
6. **Security** — CSRF, hashed passwords, no secret leakage.
7. **a11y / motion** — focus, contrast, reduced-motion.
8. **3-Loop** — review → fix → test ×3 before final.

---

## 9. Agent Kickoff Prompt

```text
agent.md(2026)를 최우선으로 따른다.
- Python 3.12+ / Flask 3.1.x / SQLAlchemy 2.0 / Flask-Migrate 4.x / Bootstrap 5.3.8
- create_app + Blueprint + .env/config.py SSOT
- 템플릿 [UI Flow] 주석, Mobbin Quicken(사이드내비·카드·프로그레스)·oklch 토큰·다크모드
- PWA + 인앱 브라우저 탈출
- Ruff/pytest 가능하면 검증, 제안 전 3회 자가 검토
- Admin seed: wecar / 1004wecar (hash, env override)
```
