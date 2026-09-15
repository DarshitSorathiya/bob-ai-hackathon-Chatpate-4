# ARCHITECTURE.md — MissionReady AI

## System Overview

MissionReady AI is a mission-readiness and predictive-maintenance decision-support platform. It ingests HUMS telemetry and service history, predicts component failure risk and remaining useful life, determines asset readiness relative to mission requirements, prioritises maintenance actions, and answers operator questions through a grounded AI copilot.

---

## High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BROWSER / OPERATOR                               │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ HTTPS  (React + Next.js 14 App Router)
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                          FRONTEND  (src/frontend/)                          │
│  /dashboard  /assets  /missions  /maintenance  /alerts                      │
│  /data-quality  /copilot  /models  /login  /signup                          │
│                                                                             │
│  TanStack Query ← REST/SSE ← lib/api.js ← NEXT_PUBLIC_API_URL              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ REST + SSE  /api/v1/*
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                           BACKEND API  (FastAPI)                            │
│  src/backend/app/                                                           │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Auth Routes  │  │ Asset Routes │  │Mission Routes│  │Maint. Routes  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └───────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Alert Routes │  │DQ Routes     │  │Model Routes  │  │Copilot Routes │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └───────────────┘  │
│                                                                             │
│  Services Layer                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │AuthService   │  │ReadinessEng. │  │MaintPriority │  │CopilotService │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └───────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                                        │
│  │MLInference   │  │AlertService  │                                        │
│  └──────────────┘  └──────────────┘                                        │
└────────┬─────────────────────────┬───────────────────────┬─────────────────┘
         │                         │                       │
         ▼                         ▼                       ▼
┌────────────────┐   ┌─────────────────────────┐  ┌───────────────────────┐
│  PostgreSQL    │   │    ML Engine (Python)   │  │   IBM watsonx.ai      │
│  (Database)    │   │                         │  │   (LLM / NL Layer)    │
│                │   │  Model A: RUL           │  │                       │
│  All tables    │   │  Model B: Failure Risk  │  │  Copilot reasoning    │
│  (see DATA_    │   │  Model C: Anomaly       │  │  Grounded on backend  │
│  MODEL.md)     │   │                         │  │  tool calls only      │
└────────────────┘   └─────────────────────────┘  └───────────────────────┘
```

---

## Data Flow: Telemetry → Readiness

```
[Simulator / Ingestion]
         │
         ▼
  telemetry table  +  telemetry_quality table
         │
         ▼
  [Preprocessing Pipeline]  (Pandas)
  - rolling windows
  - anomaly thresholds
  - feature extraction
         │
         ▼
  features table
         │
    ┌────┴────┐
    ▼         ▼
[Model A]  [Model B]  [Model C]
  RUL       Fail%      Anomaly
    │         │           │
    └────┬────┘           │
         ▼                │
  predictions table       │
         │                │
         ▼                ▼
  [Readiness Engine]  data_quality_events
  (deterministic rules)
  + mission requirements
  + maintenance status
         │
         ▼
  Asset readiness: READY / AT_RISK / NOT_READY / UNKNOWN
         │
         ▼
  alerts table  +  recommendations table
         │
    SSE push to frontend
```

---

## Data Flow: Copilot Query

```
[Operator types a question]
         │
         ▼
  POST /api/v1/copilot/query
         │
         ▼
  [CopilotService]
  - intent detection
  - tool selection (get_asset, get_predictions, get_maintenance, etc.)
         │
         ▼
  [Backend Tools]
  - read trusted DB data
  - compose structured evidence context
         │
         ▼
  [watsonx.ai Inference]
  - receives: question + structured evidence
  - never receives raw DB credentials
  - never invents telemetry values
         │
         ▼
  [Response with evidence references]
         │
         ▼
  copilot_conversations + copilot_messages + copilot_evidence tables
```

---

## Authentication & Authorization Flow

```
POST /api/v1/auth/login
         │
  (email + password OR Google ID token)
         │
  [AuthService.authenticate()]
         │
  JWT issued (sub = str(user.id))
         │
  Frontend: localStorage → missionready_access_token
         │
  Subsequent requests: Authorization: Bearer <token>
         │
  [deps.get_current_user()]
  → decode_access_token()
  → UserRepository.get_by_id()
  → inject CurrentUser
         │
  [require_roles("admin", ...)]
  → 403 if role not allowed
```

---

## Real-Time Events (SSE)

```
GET /api/v1/events  (SSE stream, authenticated)

Server pushes:
  telemetry.updated    → frontend refetches /assets/:id/telemetry
  prediction.updated   → frontend refetches /assets/:id/predictions
  alert.created        → frontend shows notification
  alert.resolved       → frontend dismisses notification
  work_order.updated   → frontend refetches /maintenance/work-orders/:id
  mission.readiness_changed → frontend refetches /missions/:id
```

---

## ML Architecture

### Model A — RUL (Regression)

| Property | Detail |
|---|---|
| Target | Hours of remaining useful life |
| Algorithm | Gradient Boosting (XGBoost/LightGBM baseline; evaluate temporal models if justified) |
| Features | Rolling window statistics, trends, operating conditions, vibration features, maintenance age |
| Output | `rul_estimate`, `rul_lower`, `rul_upper` (confidence interval) |
| Split | By asset trajectory, never by row |
| Leakage guard | `true_rul`, `true_health`, `failure_events` NEVER in feature set |

### Model B — Failure Risk (Classification)

| Property | Detail |
|---|---|
| Target | Binary failure within horizon (24h / 72h / mission window) |
| Algorithm | Gradient Boosting classifier |
| Features | Same feature set as Model A (shared feature pipeline) |
| Output | `failure_probability_24h`, `failure_probability_mission` |
| Calibration | Platt scaling or isotonic regression |

### Model C — Anomaly Detection (Unsupervised)

| Property | Detail |
|---|---|
| Target | Anomalous telemetry pattern |
| Algorithm | IsolationForest baseline; evaluate OCSVM if needed |
| Features | Sensor values relative to historical baseline per asset |
| Output | `anomaly_score` (0–1), contributing sensor indicators |

### Training Data Sources

- NASA C-MAPSS FD001–FD004 (primary engine degradation)
- NASA IMS Bearings (vibration-domain features)
- Synthetic fleet (1,000 assets with causal degradation simulator)

---

## Database Architecture

See `docs/DATA_MODEL.md` for the full schema.

Major table groups:
- **Fleet**: `assets`, `components`, `sensors`
- **Telemetry**: `telemetry`, `telemetry_quality`, `data_quality_events`
- **Maintenance**: `maintenance_events`, `work_orders`
- **Missions**: `missions`, `mission_requirements`, `mission_assignments`
- **ML**: `features`, `predictions`, `failure_events`, `model_versions`, `model_metrics`
- **Operations**: `alerts`, `recommendations`
- **AI**: `copilot_conversations`, `copilot_messages`, `copilot_evidence`
- **Security**: `users`, `roles`, `audit_logs`

---

## Readiness Engine Logic

```
INPUTS:
  latest prediction for asset  (RUL, failure_probability)
  mission_requirement.duration_hours
  maintenance status  (any open critical work orders?)
  data quality  (telemetry freshness, anomaly_score, confidence)

RULES (in priority order):
  1. If any critical work order is OPEN and BLOCKING:
     → NOT_READY

  2. If asset is currently under maintenance:
     → NOT_READY

  3. If failure_probability > 0.45 (configurable):
     → NOT_READY

  4. If rul_estimate < mission_duration * 1.25 (safety margin):
     → NOT_READY

  5. If telemetry freshness > stale_threshold OR confidence < min_confidence:
     → UNKNOWN  (unless policy allows AT_RISK on degraded data)

  6. If failure_probability > 0.15 OR rul_estimate < mission_duration * 2.0:
     → AT_RISK

  7. Else:
     → READY

OUTPUT:
  ReadinessStatus: READY | AT_RISK | NOT_READY | UNKNOWN
  reason_code: string
  contributing_factors: list
  confidence: float
```

---

## Security Architecture

See `docs/SECURITY.md` for full detail.

Key design decisions:
- JWT Bearer tokens; argon2 password hashing
- Server-side RBAC; roles enforced via `require_roles()` at route level
- All IBM/watsonx credentials server-side only; never proxied to browser
- Audit log for every state-changing action
- Rate limiting on auth endpoints
- SQL injection: SQLAlchemy ORM only; no raw string interpolation
- Secrets: `.env` file (gitignored); no secrets in source

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | Next.js 14 (App Router), React 18, TypeScript (new modules), Tailwind CSS | Existing foundation; App Router simplifies routing |
| State / Data | TanStack Query | Server state, caching, background refresh |
| Charts | Recharts | Well-supported React charting; matches dark theme easily |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 | Existing foundation; high-performance async API |
| Auth | PyJWT, pwdlib[argon2], google-auth | Existing implementation; production-quality |
| Database | PostgreSQL (psycopg v3) | ACID, time-series indexing, JSON support |
| Migrations | Alembic | Must be added; `create_all` not sufficient for schema evolution |
| ML | NumPy, Pandas, SciPy, scikit-learn, XGBoost | Standard; must be installed |
| AI Copilot | IBM watsonx.ai (ibm-watsonx-ai SDK) | Required by hackathon |
| Real-time | Server-Sent Events (SSE via FastAPI `StreamingResponse`) | Simpler than WebSocket for push-only updates |
| Containerization | Docker + Docker Compose | Local dev parity; PostgreSQL container |

---

## Directory Structure (Target)

```
src/
  backend/
    app/
      api/
        routes/          existing: auth, health
                         new: assets, missions, maintenance, alerts,
                              data_quality, models, copilot, dashboard
      core/              existing: config, database, security, roles
      models/            existing: user
                         new: asset, component, sensor, telemetry,
                              prediction, mission, work_order, alert, ...
      repositories/      one per model
      schemas/           existing: auth
                         new: per-domain schemas
      services/          existing: auth_service
                         new: readiness_engine, maintenance_priority,
                              ml_inference, copilot_service, alert_service
      ml/
        features/        feature engineering pipeline
        models/          trained model artifacts
        training/        training scripts
        evaluation/      evaluation and calibration
      data/
        raw/             downloaded datasets
        processed/       transformed features
        synthetic/       simulator output
      migrations/        Alembic migrations
    requirements.txt
    requirements-ml.txt  (ML dependencies, installed separately)
  frontend/
    app/                 existing: /, /login, /signup
                         new: /dashboard, /assets/*, /missions/*,
                              /maintenance/*, /alerts, /data-quality,
                              /copilot, /models
    components/          existing: AuthLayout, Button, GoogleButton,
                                   HumsSensorCanvas, Input
                         new: domain-specific components
    lib/                 existing: api.js
    hooks/               TanStack Query hooks (new)
    types/               TypeScript types (new)
```
