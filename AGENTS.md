# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Stack
- **Backend**: FastAPI (Python 3.12) + SQLAlchemy 2 + psycopg v3 + Alembic — lives in `src/backend/`
- **Frontend (active)**: Next.js 14, plain JS — lives in `src/frontend/`, served on port 3000
- **Frontend (preserved, do not extend)**: Vite/React 19/TypeScript — `src/frontend-new/`
- **ML**: scikit-learn, XGBoost, LightGBM, pandas/pyarrow — deps in `src/backend/requirements-ml.txt` (separate from `requirements.txt`)

## Commands

**Backend** (run from `src/backend/`):
```bash
pip install -r requirements.txt          # core deps
pip install -r requirements-ml.txt      # ML deps — install separately
pytest                                   # all tests
pytest tests/test_health.py             # single test file
pytest -k "test_name"                   # single test by name
pytest -m "not slow"                     # skip ML slow tests
ruff check app/ tests/                   # lint
ruff format app/ tests/                  # format
alembic upgrade head                     # apply migrations
```

**Frontend** (run from `src/frontend/`):
```bash
npm run dev     # dev server (port 3000)
npm run lint    # ESLint
```

## Non-Obvious Rules

### Environment & Config
- **`.env` must be at `src/.env`** — `config.py` resolves it via `Path(__file__).resolve().parents[3] / ".env"`. Any other path silently fails with no startup error.
- **`DATABASE_URL` must use `postgresql+psycopg://`** (psycopg v3). `+psycopg2` or bare `postgresql://` causes startup failure.
- **Never call `Settings()` directly** — `get_settings()` is `@lru_cache`; bypassing it breaks the cache.
- **In production**, `create_tables()` is NOT called on startup (development-only). All schema changes go through Alembic migrations.

### Backend Patterns
- **`DbSession` and `CurrentUser`** are `Annotated` type aliases in `app.api.deps` — use as type hints, not `Depends(...)` calls.
- **Role constants** in `app.core.roles`: `OPERATOR`, `MAINTAINER`, `ADMIN`. Never hardcode role strings. Enforce with `require_roles(*roles)` from `app.api.deps`.
- **Service layer raises domain exceptions** (`EmailAlreadyRegisteredError`, `InvalidCredentialsError`, `GoogleAuthenticationError`). Routes catch and convert to `HTTPException`. Never raise `HTTPException` inside services.
- **API envelope**: all routes call `make_response(data, request_id)` / `make_error(code, msg, request_id)` from `app.core.responses`. **Exception**: `/auth/register`, `/auth/login`, `/auth/me`, `/auth/google` return raw `AuthResponse`/`UserResponse` — no envelope.
- **New ORM models** must be imported in `migrations/env.py` or Alembic autogenerate won't detect them.
- **All API routes are prefixed `/api/v1`** — hardcoded in `main.py`'s `include_router()` calls, not configurable.

### Testing
- **`asyncio_mode = "auto"`** in `pyproject.toml` — async tests work without `@pytest.mark.asyncio`.
- **Tests use SQLite in-memory**, not PostgreSQL. See `tests/conftest.py`. `reset_db` fixture is `autouse=True`, recreating tables for every test.
- **`pytest` must be run from `src/backend/`** — `pyproject.toml` is there; running from repo root fails.
- **Slow ML tests** are marked `@pytest.mark.slow`; skip with `-m "not slow"`.

### Frontend
- **`'use client'` must be the first line** of every file in `src/frontend/` — no server components used.
- **`saveSession(authResponse)`** in `src/frontend/lib/api.js` must be used for writing auth to localStorage. Never write `missionready_access_token` / `missionready_user` keys directly.
- **`Button` component defaults `fullWidth=true`** — always pass `fullWidth={false}` explicitly for inline buttons.
- **Two CSS systems active simultaneously** in `src/frontend/`: `app/globals.css` (Tailwind) and `public/styles.css` (imported in `layout.jsx`).

### ML Pipeline
- **Leakage guard**: `true_rul`, `true_health`, `failure_events`, `failure_label` must never appear in feature DataFrames passed to model training.
- **Provenance sidecar required**: every processed dataset output must have a `.provenance.json` sidecar written via `app.ml.ingestion.provenance.write_provenance()`.
- **C-MAPSS and IMS datasets must never be merged** — they model different degradation regimes and must be treated as separate input streams.
