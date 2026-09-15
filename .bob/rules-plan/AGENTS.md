# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Architectural Constraints

- **Active frontend is `src/frontend/`** (Next.js 14, plain JS) — not `src/frontend-new/`. The two apps share the same FastAPI backend but have separate npm workspaces and separate API clients. No shared code between them.
- **`.env` location is structurally hardcoded** — `config.py` uses `Path(__file__).resolve().parents[3]` to locate `src/.env`. Architectural components that need env vars must use `get_settings()` (cached singleton), not direct `os.getenv()` calls.
- **Auth routes bypass the envelope** — `/auth/register`, `/auth/login`, `/auth/me`, `/auth/google` return raw `AuthResponse`/`UserResponse`. All other routes must use `make_response()`/`make_error()` from `app.core.responses`. The frontend `request()` wrapper accounts for this distinction.
- **Alembic is the only schema management path** — `create_all()` exists in `database.py` for test setup only. All new models must add an Alembic migration AND be imported in `migrations/env.py`.
- **Role system is a flat allowlist** — `OPERATOR`, `MAINTAINER`, `ADMIN` in `app.core.roles`. No hierarchy. `require_roles()` is an allowlist check only. New roles need to be added to both `roles.py` and `ALL_ROLES`.
- **Dual auth provider design** — a user can have both `password_hash` and `google_subject` set simultaneously (Google login merges into an existing password account). New auth providers must follow the merge-or-create pattern in `AuthService`.
- **All routes prefixed `/api/v1`** — hardcoded in `main.py`'s `include_router()` calls. Not configurable via settings.
- **ML pipeline is isolated in `app/ml/`** — ingestion, validation, feature engineering, training, evaluation are separate sub-packages. ML deps in `requirements-ml.txt` must be installed separately before any ML work.
- **Leakage guard is architectural** — `true_rul`, `true_health`, `failure_events`, `failure_label` must never flow into model feature DataFrames. The validation module enforces this at test time; enforce it at design time too.
- **Provenance is required for every processed output** — `app.ml.ingestion.provenance` must generate a `.provenance.json` sidecar alongside every Parquet file written. This is a data governance constraint, not optional.
- **C-MAPSS and IMS are never merged** — they are separate behavioral reference sources for different degradation regimes. Any multi-dataset model must treat them as distinct input streams.
- **`src/frontend/` has no state management** — auth state is read directly from `localStorage`. Global state requires adding a Context provider in `layout.jsx`.
- **`src/frontend-new/` uses only TanStack Query + React Context** — no global UI state library. Adding global state requires a new Context or a library.
