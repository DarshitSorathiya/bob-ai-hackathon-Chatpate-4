# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Documentation Context

- **Active frontend is `src/frontend/`** (Next.js 14, plain JS) — this was originally labeled "legacy" but is now the actively developed app with the full fleet dashboard. `src/frontend-new/` (Vite/React 19/TypeScript) is a preserved Phase 2 stub that is no longer extended.
- **`src/frontend/`** contains: animated landing page (`LandingRadarCanvas`, `HumsSensorCanvas` canvas components), login/signup pages, and a full fleet dashboard at `/dashboard`. It serves on port 3000.
- **`src/.env`** is the canonical environment config — the README's `.env.example` shows older schema; the actual pydantic-settings model in `config.py` uses `jwt_secret_key`, `cors_origins`, `database_url`, etc.
- **Auth routes return raw responses** — `/auth/register`, `/auth/login`, `/auth/me`, `/auth/google` do NOT use the `{success, data, meta, error}` envelope. All other routes do.
- **`src/frontend/lib/api.js`** (active) and **`src/frontend-new/src/lib/api.ts`** (preserved) are separate clients for the two frontends, both calling the same FastAPI backend.
- **`.venv/` is at the repo root**, not inside `src/backend/`. `requirements.txt` is at `src/backend/requirements.txt`. ML packages are in a separate `requirements-ml.txt`.
- **`docs/IMPLEMENTATION_PLAN.md`** is the authoritative phase roadmap — check it for actual completion status, not the README feature tables.
- **`src/backend/app/ml/`** contains data ingestion, validation, and simulator code — ingestion (Phase 3) is not yet tested against real datasets; the simulator (Phase 4) has 28/28 tests passing.
- **Google OAuth** is partially wired: backend has `/auth/google` endpoint and `authenticate_google()` in `AuthService`; the `GoogleButton` component in `src/frontend/` is a non-functional stub unless a real `onClick` prop is provided.
- **Two separate CSS systems in `src/frontend/`** — `app/globals.css` (Tailwind directives) and `public/styles.css` (imported in `layout.jsx`) — both are active simultaneously.
