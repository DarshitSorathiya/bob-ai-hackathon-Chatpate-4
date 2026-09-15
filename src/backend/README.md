# MissionReady FastAPI Backend

## Structure

- `app/core`: configuration, database connection, and security primitives
- `app/models`: SQLAlchemy persistence models
- `app/schemas`: request and response validation
- `app/repositories`: database access only
- `app/services`: authentication business rules
- `app/api`: HTTP dependencies and route handlers

## Setup

From `src/`, copy `.env.example` to `.env` and set the PostgreSQL credentials and a long JWT secret.

```bash
cd src/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Run the command from `src/backend`. The option is `--reload` (not
`--relaod`). `DATABASE_URL` must point to a running PostgreSQL database such as
Neon; the backend does not start when that database is unreachable.

The API docs are available at `http://localhost:8000/docs`.

## Auth endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/google` with a Google OAuth ID token
- `GET /api/v1/auth/me` with `Authorization: Bearer <token>`
- `POST /api/v1/auth/forgot-password`
- `GET /api/v1/health`

## Frontend field contract

Signup accepts `fullName`, `email`, `password`, and `confirmPassword`.
Login accepts `email` and `password`. The backend also accepts snake_case aliases
for the signup fields. Google sign-in must send the ID token returned by Google
as `{ "id_token": "..." }`; the backend verifies it and never trusts a client
provided email or role.

New accounts default to the `operator` role. Available role constants are
`operator`, `maintainer`, and `admin`. Protect future routes with
`Depends(require_roles("admin"))` from `app.api.deps`.

For an existing database, add the new `role`, `google_subject`, and
`auth_provider` columns with a migration before deploying. `create_all` only
creates missing tables; it does not alter an existing `users` table.
