# RESEARCH.md — MissionReady AI

## 1. Repository Inspection Summary

### Files Inspected

| Path | Status |
|---|---|
| `README.md` | Complete project description (hackathon narrative) |
| `submission.yaml` | Submission metadata — all required fields filled |
| `CONTRIBUTING.md` | Hackathon template instructions |
| `.gitignore` | Standard; ignores `.env`, `data/`, `logs/`, `node_modules/`, `.venv/` |
| `.github/workflows/validate.yml` | CI checks for required file presence and non-placeholder content |
| `docs/architecture.md` | **Template placeholder — no real architecture yet** |
| `docs/problem-statement.md` | **Template placeholder — no real content yet** |
| `docs/solution-overview.md` | **Template placeholder — no real content yet** |
| `docs/setup-guide.md` | **Template placeholder — no real content yet** |
| `src/.env.example` | Defines all required env vars (see §4) |
| `src/backend/requirements.txt` | Backend Python dependencies |
| `src/backend/app/main.py` | FastAPI entrypoint — auth + health routes only |
| `src/backend/app/core/` | Config, database (SQLAlchemy 2), security (JWT + argon2) |
| `src/backend/app/models/user.py` | Users table only |
| `src/backend/app/schemas/auth.py` | Auth schemas with AliasChoices |
| `src/backend/app/services/auth_service.py` | Register, login, Google OAuth |
| `src/backend/app/api/routes/auth.py` | Auth endpoints |
| `src/backend/app/api/deps.py` | `DbSession`, `CurrentUser`, `require_roles()` |
| `src/backend/app/core/roles.py` | `OPERATOR`, `MAINTAINER`, `ADMIN` constants |
| `src/frontend/package.json` | Next.js 14, React 18, lucide-react, Tailwind |
| `src/frontend/app/` | App Router: `/`, `/login`, `/signup` |
| `src/frontend/components/` | `AuthLayout`, `Button`, `GoogleButton`, `HumsSensorCanvas`, `Input` |
| `src/frontend/lib/api.js` | Central API client with error handling |

### What Exists (Implemented)

- Authentication: register, login, Google OAuth, JWT, argon2 password hashing
- Role constants (operator, maintainer, admin) and `require_roles()` guard
- Next.js frontend with landing page + login/signup forms
- Animated HUMS sensor canvas background
- No ML models, no telemetry, no readiness engine, no missions, no maintenance engine, no copilot

### What Does Not Exist Yet

Everything specified in the product spec beyond authentication.

---

## 2. Runtime Environment

| Tool | Version | Location |
|---|---|---|
| Python | 3.12.3 | System |
| Node.js | 24.20.0 | System |
| npm | 11.19.0 | System |
| PostgreSQL | Not installed locally | Needs Docker or remote |
| Docker | Not installed locally | Needs installation or cloud DB |
| psql CLI | Not in PATH | — |

### Python Virtual Environment (`.venv/`)

Currently installed packages relevant to the product:

| Package | Version | Notes |
|---|---|---|
| fastapi | 0.115.6 | ✅ |
| uvicorn | 0.34.0 | ✅ |
| SQLAlchemy | 2.0.36 | ✅ |
| psycopg (v3) | 3.2.3 | ✅ |
| pydantic-settings | 2.7.1 | ✅ |
| pydantic | 2.13.5 | ✅ |
| PyJWT | 2.10.1 | ✅ |
| pwdlib[argon2] | 0.2.1 | ✅ |
| google-auth | 2.37.0 | ✅ |
| pytest | 8.3.4 | ✅ |
| httpx | 0.28.1 | ✅ (test client) |
| **numpy** | ❌ not installed | Required for ML |
| **pandas** | ❌ not installed | Required for ML |
| **scikit-learn** | ❌ not installed | Required for ML |
| **scipy** | ❌ not installed | Required for ML |
| **xgboost/lightgbm** | ❌ not installed | Required for ML |
| **alembic** | ❌ not installed | Required for migrations |

### Frontend Dependencies

| Package | Version |
|---|---|
| next | ^14.2.15 |
| react | ^18.3.1 |
| react-dom | ^18.3.1 |
| lucide-react | ^0.453.0 |
| tailwindcss | ^3.4.14 |
| **Missing: axios / TanStack Query / Recharts / ECharts** | Will need to be added |

---

## 3. Existing Code Quality Assessment

### Backend

**Strengths:**
- Clean layered architecture: models → repositories → services → routes
- Proper Annotated type aliases for DI (`DbSession`, `CurrentUser`)
- Domain exceptions (`EmailAlreadyRegisteredError`, `InvalidCredentialsError`)
- Google OAuth correctly verifies ID token server-side
- Argon2 password hashing (best practice)
- `@lru_cache` on settings singleton

**Issues / Gaps:**
- No database migration tool (only `create_all`); must add Alembic before expanding schema
- No test files at all — `pytest` is installed but no tests written
- `forgot-password` endpoint is a stub (returns static message, sends no email)
- No structured logging, no request IDs
- No rate limiting
- `DATABASE_URL` uses psycopg v3 driver (`postgresql+psycopg://`) — must be consistent across all future work

### Frontend

**Strengths:**
- Clean component decomposition
- Central API client with proper error normalization
- Accessible `Input` component (aria-invalid, aria-describedby)
- Animated HUMS background is polished and thematically appropriate

**Gaps:**
- No state management (no TanStack Query, no Zustand/Context)
- No routing guards (protected routes)
- Only `.jsx` files — spec calls for TypeScript consideration
- No test infrastructure

---

## 4. Environment Variables

From `src/.env.example`:

```
WATSONX_API_KEY         IBM watsonx.ai API key
WATSONX_PROJECT_ID      IBM watsonx.ai project ID
WATSONX_URL             https://us-south.ml.cloud.ibm.com
DATABASE_URL            postgresql+psycopg://...  (psycopg v3)
APP_PORT                8000
APP_ENV                 development
JWT_SECRET_KEY          Long random secret
JWT_ALGORITHM           HS256
ACCESS_TOKEN_EXPIRE_MINUTES  60
CORS_ORIGINS            http://localhost:3000
GOOGLE_CLIENT_ID        Google OAuth web client ID
NEXT_PUBLIC_API_URL     http://localhost:8000/api/v1
SLACK_WEBHOOK_URL       (optional)
```

---

## 5. Git Branch Summary

| Branch | Purpose |
|---|---|
| `main` | Initial scaffolding commit |
| `tulsi-auth` | Auth implementation (current working branch) |
| `origin/backend` | Remote backend branch |
| `origin/frontend` | Remote frontend branch |

---

## 6. Datasets Available

**None currently present in the repository.**

Required datasets must be acquired:

| Dataset | Source | Notes |
|---|---|---|
| NASA C-MAPSS | [NASA PCoE](https://www.nasa.gov/content/prognostics-center-of-excellence-data-set-repository) | Turbofan engine RUL; FD001–FD004; ~20 MB |
| NASA IMS Bearings | [UCI/NASA](https://www.nasa.gov/content/prognostics-center-of-excellence-data-set-repository) | Vibration degradation; ~300 MB compressed |
| AI4I 2020 (optional) | [UCI Repository](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset) | Supplementary classification; ~500 KB |

None of these are present in the repository; they must be downloaded as part of Phase 4.

---

## 7. Conflicts and Ambiguities

| Item | Description | Resolution |
|---|---|---|
| Backend README says `cd src/backend && uvicorn app.main:app` | AGENTS.md says `uvicorn src.backend.app.main:app` from repo root | Either works; standardize on `cd src/backend` to match existing README |
| `docs/*.md` are all template placeholders | GitHub Actions validate they exist but do not check content | Will be replaced with real content during Phase 1 documentation |
| Docker not installed locally | Spec calls for Docker Compose | Will use a remote/cloud PostgreSQL or install Docker; document both paths |
| Frontend uses `.jsx` not `.tsx` | Spec mentions TypeScript as preferred | Maintain `.jsx` for existing files; introduce TypeScript for new feature modules |
| No Alembic migrations | `create_all()` only creates new tables | Must add Alembic before any new schema work to avoid data loss |
| No ML packages in `.venv` | ML is Phase 6+ | Install NumPy/Pandas/scikit-learn/XGBoost in Phase 4 |
| `forgot-password` is a stub | Returns static message | Acceptable for hackathon; document known limitation |

---

## 8. Key Findings

1. **Foundation is solid.** Authentication, RBAC scaffolding, and frontend auth flow are production-quality.
2. **No application logic beyond auth exists.** Every product feature (telemetry, ML, readiness, maintenance, copilot) must be built from scratch.
3. **No database migration tool.** Alembic must be installed and configured before Phase 3 schema work.
4. **No datasets present.** Must be downloaded and documented before ML phases.
5. **No ML dependencies installed.** NumPy, Pandas, scikit-learn, XGBoost, SciPy must be added to `requirements.txt`.
6. **No test suite.** Pytest is installed but zero tests exist. Testing infrastructure must be established in Phase 2.
7. **PostgreSQL is not available locally.** The project needs either Docker or a cloud database URI in `.env`.
8. **Frontend lacks TanStack Query and charting libraries.** These must be added for the dashboard work in Phase 12.
