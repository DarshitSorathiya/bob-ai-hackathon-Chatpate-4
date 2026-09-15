# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Overview

MissionReady AI — Mission Readiness & Predictive Maintenance Copilot (IBM Bob Hackathon, Team Chatpate-4).
FastAPI (Python 3.12) backend + two frontend layers.

Read `docs/IMPLEMENTATION_PLAN.md` before implementing new phases.

## Two Frontends — Know Which Is Active

- **`src/frontend/`** — **ACTIVE** app (Next.js 14 App Router, React 18, plain JS, Tailwind). All new feature work goes here. Has landing page, login, signup, and full fleet dashboard.
- **`src/frontend-new/`** — **preserved but not extended** (Vite + React 19 + TypeScript + TanStack Query + React Router 7). Phase 2 stub only; no new work added here.
- Legacy `lib/api.js` uses raw `fetch`; `frontend-new` uses Axios in `lib/api.ts`. Both call the same FastAPI backend.

## Repository Layout

```
src/
  .env                  # ← must exist here (NOT at repo root)
  backend/              # run all backend commands from here
  frontend/             # ACTIVE Next.js 14 frontend (port 3000)
  frontend-new/         # preserved Vite/TS stub (port 5173)
.venv/                  # venv at REPO ROOT, not inside src/backend/
```

## Commands

### Backend — run from `src/backend/`
```bash
source .venv/bin/activate          # venv at REPO ROOT

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

pytest                             # all tests
pytest tests/test_health.py        # single file
pytest -k test_health_returns_200  # single test

alembic upgrade head
alembic revision --autogenerate -m "description"

python scripts/download_datasets.py --dataset cmapss
python scripts/preprocess_cmapss.py
python scripts/preprocess_ims.py
```

### Frontend (active) — run from `src/frontend/`
```bash
cd src/frontend
npm run dev        # http://localhost:3000
npm run build
```

### Frontend (preserved) — run from `src/frontend-new/`
```bash
cd src/frontend-new
npm run dev        # http://localhost:5173
npm run typecheck
npm run lint       # oxlint
npm run build
```

## Critical Environment Setup

- **`.env` lives at `src/.env`** — `config.py` hardcodes resolution as `Path(__file__).resolve().parents[3] / ".env"`. Any other location silently fails.
- `DATABASE_URL` must use `postgresql+psycopg://` prefix (psycopg **v3**) — not `postgresql://` or `+psycopg2`.
- `JWT_SECRET_KEY` ≥ 32 random bytes.
- `CORS_ORIGINS` is comma-separated; defaults include both port `5173` (Vite) and `3000` (Next.js).
- Active frontend reads `NEXT_PUBLIC_API_URL` from `src/frontend/.env.local`.

## Backend Patterns

- **API envelope** — every route returns `make_response(data, request_id)` or `make_error(code, msg, request_id)` from `app.core.responses`. **Exception: auth routes** (`/auth/register`, `/auth/login`, `/auth/me`, `/auth/google`) return raw `AuthResponse`/`UserResponse` — no envelope.
- **Request ID** — available via `request.headers.get("X-Request-ID", "")` (set by `RequestIDMiddleware`).
- **DI aliases** — `DbSession` and `CurrentUser` are `Annotated` aliases in `app.api.deps`; use as type hints, not `Depends(...)`.
- **Role guard** — `require_roles(*roles)` from `app.api.deps`; role constants in `app.core.roles` (`OPERATOR`, `MAINTAINER`, `ADMIN`).
- **Service exceptions** — services raise domain exceptions; routes catch and convert to `HTTPException`. Never raise `HTTPException` inside services.
- **`get_settings()` is `@lru_cache`** — never call `Settings()` directly.
- **New ORM models** — must be imported in `migrations/env.py` for Alembic autogenerate to detect them.
- **JWT subject** is `str(user.id)` (integer serialized as string).

## Frontend Patterns (Active — `src/frontend/`)

- **`'use client'`** must be the first line of every page and component file — no server components are used.
- All API calls go through `lib/api.js` `request()` wrapper — it normalises FastAPI `detail` array errors and attaches the Bearer token automatically.
- `saveSession(authResponse)` writes token + user to localStorage — never write `missionready_access_token` / `missionready_user` keys directly.
- `Button` defaults `fullWidth=true`; pass `fullWidth={false}` for inline buttons.
- `GoogleButton` without an `onClick` prop is a non-functional stub.
- Two CSS systems active simultaneously: `app/globals.css` (Tailwind directives) and `public/styles.css` (imported in `layout.jsx`).
- Auth routes return raw responses; `lib/api.js` detects this and does NOT unwrap the envelope for those calls.

## Frontend Patterns (Preserved — `src/frontend-new/`)

- All API calls through `lib/api.ts` via `authApi.*` or `systemApi.*`. Never call axios/fetch directly from components.
- Auth state via `useAuth()` from `contexts/AuthContext.tsx`. Token at localStorage key `missionready_access_token`.
- `tokenStorage.*` helpers in `lib/api.ts` must be used to read/write auth tokens — never `localStorage.setItem` directly.
- TanStack Query — all server state in `src/hooks/`. Components never call API functions directly.
- Path alias `@/` → `src/frontend-new/src/` (both `vite.config.ts` and `tsconfig.app.json`).

## Code Style

### Python
- Python 3.12+; type annotations on all signatures; `X | Y` unions (not `Optional[X]`).
- Line length 100 (ruff). Target rules: E, F, W, I, N, UP, B, A, C4, RET.
- `asyncio_mode = "auto"` in `pyproject.toml` — async test functions work without `@pytest.mark.asyncio`.
- Pytest runs from `src/backend/` — `pyproject.toml` is there; running from repo root won't find tests.

### TypeScript / JavaScript
- Active frontend is plain JS (`.jsx`, `.js`) — no TypeScript. No `any`, no implicit types.
- Named exports for utilities/hooks; default exports for page/layout components.
- `async/await` throughout (no `.then/.catch` chains).

## ML Pipeline

- Lives under `src/backend/app/ml/` — ingestion, validation, features, models, training, evaluation.
- ML deps in `requirements-ml.txt` — install separately; not in `requirements.txt`.
- **Leakage guard** — `true_rul`, `true_health`, `failure_events`, `failure_label` must NEVER appear in feature DataFrames.
- **Provenance required** — every processed dataset output must have a `.provenance.json` sidecar written by `app.ml.ingestion.provenance`.
- **C-MAPSS and IMS are never merged** — treat as distinct input streams for all model design.
- Phase 3 ingestion code is written but not yet tested against real data.
