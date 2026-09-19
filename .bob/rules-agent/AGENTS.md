# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Coding Rules

- **`.env` at `src/.env`** — `config.py` resolves it as `Path(__file__).resolve().parents[3] / ".env"`. Any other path silently fails (no error at startup, just missing settings).
- **`DATABASE_URL` prefix** must be `postgresql+psycopg://` (psycopg v3). `+psycopg2` or bare `postgresql://` causes startup failure.
- **`DbSession` and `CurrentUser`** are `Annotated` type aliases in `app.api.deps` — use them as type hints on function parameters, not as `Depends(...)` calls.
- **`get_settings()` is `@lru_cache`** — never call `Settings()` directly or the cache is bypassed.
- **Role constants** live in `app.core.roles` — never hardcode strings like `"admin"`. Use `require_roles(*roles)` from `app.api.deps`, not inline checks.
- **Service layer raises domain exceptions** (`EmailAlreadyRegisteredError`, `InvalidCredentialsError`, `GoogleAuthenticationError`) — routes catch them and convert to `HTTPException`. Never raise `HTTPException` inside service classes.
- **JWT subject is `str(user.id)`** — `deps.py` checks `user_id.isdigit()` before converting; decode returns a string.
- **New ORM model** must be imported in `migrations/env.py` (where other models are listed) for Alembic autogenerate to detect it.
- **API envelope** — every route calls `make_response(data, request_id)` or `make_error(code, msg, request_id)` from `app.core.responses`. **Auth routes are the exception** — `/auth/register`, `/auth/login`, `/auth/me`, `/auth/google` return raw `AuthResponse`/`UserResponse` with no envelope wrapper.
- **`asyncio_mode = "auto"`** in `pyproject.toml` — async test functions work without `@pytest.mark.asyncio`.
- **pytest runs from `src/backend/`** — `pyproject.toml` is there; running `pytest` from repo root won't find tests.
- **Slow ML tests** are marked `@pytest.mark.slow`; skip with `pytest -m "not slow"`.
- **Tests use SQLite in-memory** (not PostgreSQL) — `reset_db` fixture is `autouse=True` and recreates schema for every test function.
- **Active frontend is `src/frontend/`** (Next.js 14, plain JS). `src/frontend-new/` (Vite/React 19/TypeScript) is preserved but not extended. All new page/component work goes in `src/frontend/`.
- **`'use client'`** must be the first line of every file in `src/frontend/` — no server components are in use.
- **Legacy frontend `Button` defaults `fullWidth=true`** — always pass `fullWidth={false}` explicitly for inline buttons.
- **`saveSession(authResponse)`** in `src/frontend/lib/api.js` must be used for writing session to localStorage — never write `missionready_access_token` / `missionready_user` keys directly.
- **`lib/api.js` `request()` auto-detects** auth vs envelope responses — auth routes (`/auth/*`) skip envelope unwrapping; all other routes expect `{success, data, meta, error}` structure.
- **`tokenStorage.*` helpers** in `src/frontend-new/src/lib/api.ts` must be used for the preserved frontend — never `localStorage.setItem/getItem` directly for auth keys.
- **ML pipeline code** lives under `src/backend/app/ml/`. ML deps are in `requirements-ml.txt` — install separately; not included in `requirements.txt`.
- **Leakage guard** — `true_rul`, `true_health`, `failure_events`, `failure_label` must never appear in feature DataFrames passed to model training.
- **Provenance sidecar** — every processed dataset output must have a `.provenance.json` sidecar written by `app.ml.ingestion.provenance.write_provenance()`.
- **C-MAPSS and IMS must never be merged** — treat as separate input streams for all multi-dataset model work.
- **All API routes prefixed `/api/v1`** — hardcoded in `main.py`'s `include_router()` calls, not a configurable setting.
- **`create_tables()` is development/test only** — in production, Alembic owns all schema changes. Never call it from application logic.
