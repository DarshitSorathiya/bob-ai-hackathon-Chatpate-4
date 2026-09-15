# Setup Guide — MissionReady AI

> Complete local development environment setup.
> Read in full before starting — there are several non-obvious steps.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | [python.org](https://python.org) or `pyenv` |
| Node.js | 18+ (24 recommended) | [nodejs.org](https://nodejs.org) or `nvm` |
| npm | 9+ | bundled with Node |
| Docker Desktop | 24+ | [docker.com](https://docker.com) — **for PostgreSQL** |
| Git | any | — |

Docker is required for the local PostgreSQL instance. Alternatively, use a
cloud database (Neon/Supabase free tier) and set `DATABASE_URL` directly.

---

## 1 — Clone the Repository

```bash
git clone https://github.com/DarshitSorathiya/bob-ai-hackathon-Chatpate-4.git
cd bob-ai-hackathon-Chatpate-4
```

---

## 2 — Configure Environment Variables

```bash
cp src/.env.example src/.env
```

Open `src/.env` and fill in:

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | Yes | See §3 for Docker default — must use `postgresql+psycopg://` prefix |
| `JWT_SECRET_KEY` | Yes | Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `WATSONX_API_KEY` | Copilot only | IBM Cloud → watsonx.ai → Project → API key |
| `WATSONX_PROJECT_ID` | Copilot only | IBM Cloud → watsonx.ai → Project → Project ID |
| `GOOGLE_CLIENT_ID` | Optional | Leave blank to disable Google sign-in |

**Critical:** The backend reads `src/.env` — not the repo root, not `src/backend/.env`.

---

## 3 — Start PostgreSQL

### Option A — Docker (recommended)

```bash
docker compose up db -d
```

The database will be available at `localhost:5432`.
Docker Compose default credentials match the `DATABASE_URL` in `.env.example`:

```
DATABASE_URL=postgresql+psycopg://missionready:missionready_dev_password@localhost:5432/missionready
```

### Option B — Cloud database (Neon / Supabase)

1. Create a free project.
2. Copy the connection string.
3. Replace `DATABASE_URL` in `src/.env`:
   ```
   DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname?sslmode=require
   ```

---

## 4 — Backend Setup

```bash
# Create virtual environment at repo root (one-time)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install all backend dependencies (includes ML packages)
pip install -r src/backend/requirements.txt
pip install -r src/backend/requirements-ml.txt

# Run database migrations
cd src/backend
alembic upgrade head

# (Optional) Seed demo data — creates 3 assets, components, sensors, 1 mission, alerts etc.
python scripts/seed_demo_data.py

# Start the backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

The server will print an error and exit if `DATABASE_URL` is missing or the
database is unreachable.

### Run backend tests

```bash
cd src/backend
source ../../.venv/bin/activate
pytest                                           # all tests (133 pass)
pytest tests/test_health.py                     # health endpoint only
pytest tests/ml/test_readiness_engine.py        # 128 readiness engine tests
pytest -k test_health_returns_200               # single test by name
```

---

## 5 — Frontend Setup (Active: Next.js 14)

```bash
cd src/frontend
npm install

# Set the backend API URL (only needed if not on localhost:8000)
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local

npm run dev
```

Frontend: http://localhost:3000

All pages require login. Use the signup page to create an account, or use the
seeded demo data (seed script creates no users — register via /signup).

### Build for production

```bash
cd src/frontend
npm run build
```

---

## 6 — Database Migrations

Alembic manages all schema migrations. Run from `src/backend/`:

```bash
cd src/backend
source ../../.venv/bin/activate

# Apply all pending migrations (run this after every pull)
alembic upgrade head

# Check current revision
alembic current

# Roll back one revision
alembic downgrade -1

# Generate a new migration after changing ORM models
alembic revision --autogenerate -m "describe the change"
```

**Note:** `create_tables()` runs SQLAlchemy `create_all()` on every startup as a
fallback for the demo environment — this is safe for development but Alembic
migrations are the authoritative schema management tool.

---

## 7 — Seed Demo Data

The seed script creates a realistic starting dataset:

```bash
cd src/backend
source ../../.venv/bin/activate

python scripts/seed_demo_data.py           # safe to run if already seeded
python scripts/seed_demo_data.py --reset   # wipe and re-seed from scratch
```

**Seeded data:**

| Entity | Count | Details |
|---|---|---|
| Assets | 3 | AH-64-01 (helicopter), F-16-01 (fixed-wing), HMMWV-01 (ground vehicle) |
| Components | 6 | 2 per asset — engine + rotor/avionics/transmission |
| Sensors | 12 | 2 per component — temperature, vibration, RPM, pressure |
| Mission | 1 | OPE-NIGHTHAWK-01 (PLANNED, 4h, requires helicopter + fixed-wing) |
| Work Orders | 3 | IMMEDIATE (rotor vibration), URGENT (EGT trend), SCHEDULED (service) |
| Alerts | 3 | critical + warning + info |
| DQ Events | 3 | sensor fault + calibration drift + stale data |
| Readiness | 3 | All seeded as UNKNOWN — run evaluate endpoint to compute |

After seeding, call the readiness evaluate endpoint for each asset to compute
initial readiness states:

```bash
# Replace <asset_id> with actual UUIDs from GET /api/v1/assets
curl -X POST http://localhost:8000/api/v1/readiness/evaluate/<asset_id> \
  -H "Authorization: Bearer <your_token>"
```

---

## 8 — Watsonx.ai Copilot

The copilot is enabled when `WATSONX_API_KEY` and `WATSONX_PROJECT_ID` are set
in `src/.env`. Without credentials it gracefully degrades — it still retrieves
evidence from the backend but returns a structured summary instead of a
Granite-generated narrative.

```bash
# In src/.env:
WATSONX_API_KEY=your_api_key_here
WATSONX_PROJECT_ID=your_project_id_here
WATSONX_URL=https://us-south.ml.cloud.ibm.com   # default
```

The Copilot page is at http://localhost:3000/copilot.

---

## 9 — Full Stack with Docker Compose

```bash
# Start everything (PostgreSQL + backend)
docker compose up --build

# Database only
docker compose up db -d

# Stop all
docker compose down

# Stop and remove data volumes
docker compose down -v
```

---

## Application Pages

| URL | Description | Auth required |
|---|---|---|
| `/` | Landing page | No |
| `/login` | Login | No |
| `/signup` | Register | No |
| `/dashboard` | Fleet readiness overview | Yes |
| `/assets` | Asset list with readiness badges | Yes |
| `/assets/[id]` | Asset detail — predictions, components, sensors, alerts | Yes |
| `/missions` | Mission list + create | Yes |
| `/missions/[id]` | Mission detail + readiness evaluation + assign assets | Yes |
| `/maintenance` | Priority queue + work orders + create | Yes |
| `/alerts` | Alert list + acknowledge | Yes |
| `/data-quality` | Data quality events + summary | Yes |
| `/copilot` | Grounded AI copilot chat | Yes |
| `/models` | ML model registry (MAINTAINER/ADMIN only) | Yes |

---

## API Summary

Base URL: `http://localhost:8000/api/v1`

| Prefix | Resource |
|---|---|
| `/auth` | Register, login, me, Google OAuth |
| `/health` | Health check |
| `/assets` | Fleet assets CRUD + sub-resources |
| `/readiness` | Fleet readiness summary + per-asset evaluate |
| `/missions` | Mission CRUD + readiness evaluation |
| `/maintenance` | Work orders CRUD + priority queue |
| `/alerts` | Alert list + acknowledge |
| `/data-quality` | Data quality events + summary |
| `/copilot` | Natural-language query endpoint |
| `/models` | ML model registry (MAINTAINER/ADMIN) |

Full interactive documentation: http://localhost:8000/docs

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `DATABASE_URL` validation error | Check `src/.env` exists and uses `postgresql+psycopg://` prefix |
| Backend can't connect to DB | Ensure `docker compose up db -d` is running; wait 10s for healthcheck |
| `JWT_SECRET_KEY` validation error | Generate a proper 32-byte secret and set it in `src/.env` |
| Frontend "Module not found" | Run `npm install` from `src/frontend/` |
| Frontend "Cannot reach backend" | Ensure backend is running on port 8000; check `NEXT_PUBLIC_API_URL` |
| `alembic upgrade head` fails | Ensure `DATABASE_URL` in `src/.env` points to a running database |
| Port 5432 already in use | Another PostgreSQL is running — stop it or change the port in `docker-compose.yml` |
| Models page shows "Access restricted" | Log in with a MAINTAINER or ADMIN role account |
| Copilot returns no LLM narrative | Set `WATSONX_API_KEY` and `WATSONX_PROJECT_ID` in `src/.env` |
| `pydantic_core` import error | Reinstall: `pip install -r src/backend/requirements.txt` |
