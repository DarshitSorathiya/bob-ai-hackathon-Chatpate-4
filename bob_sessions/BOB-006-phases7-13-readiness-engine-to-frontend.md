# BOB-006 — Phases 7–13: Readiness Engine, Mission Engine, Maintenance Prioritizer, Full Backend API, Frontend UI, Copilot, RBAC

**Session:** BOB-006  
**Phases:** 7–13  
**Date:** 2025  
**Status:** ✅ COMPLETE — 133/133 tests pass, all frontend pages functional

---

## Objective

Implement the full MissionReady AI platform end-to-end:

- **Phase 7** — Explainable Readiness Engine (deterministic, no LLM)
- **Phase 8** — Mission Engine (capability gaps, substitutions, conflicts, risk)
- **Phase 9** — Maintenance Prioritizer (weighted formula, urgency levels)
- **Phase 10** — Backend `/api/v1` over real DB/service layers
- **Phase 11** — Frontend mission-operations UI (all pages, no mocks)
- **Phase 12** — watsonx.ai Copilot (grounded, LLM explains evidence only)
- **Phase 13** — Security/RBAC (AuditLog, role guards, audit entries)

---

## Phase 7 — Explainable Readiness Engine

### Package: `src/backend/app/ml/readiness/`

| Module | Responsibility |
|---|---|
| `__init__.py` | Package exports |
| `models.py` | All domain types: `ReadinessStatus` (READY/AT_RISK/NOT_READY/UNKNOWN), `ReasonCode` (18 values), `ContributingFactor`, `ReadinessInput`, `ReadinessOutput`, `ReadinessThresholds`, `ComponentState`, `MaintenanceStatus` |
| `engine.py` | `ReadinessEngine` — 13 rules R1–R12+READY, deterministic, no LLM |

### Rules (in precedence order — NOT_READY > UNKNOWN > AT_RISK > READY)

| Rule | Trigger | Status |
|---|---|---|
| R1 | Asset under critical maintenance | NOT_READY |
| R2 | Critical component failure | NOT_READY |
| R3 | RUL below mission requirement | NOT_READY |
| R4 | Failure probability above critical threshold | NOT_READY |
| R5 | Sensor fault on critical sensor | NOT_READY |
| R6 | Overdue critical maintenance | NOT_READY |
| R7 | Stale critical telemetry | UNKNOWN |
| R8 | Insufficient data / no predictions | UNKNOWN |
| R9 | Data quality below minimum threshold | UNKNOWN |
| R10 | Multiple degraded components | AT_RISK |
| R11 | High failure probability (warning band) | AT_RISK |
| R12 | RUL in warning band | AT_RISK |
| READY | No triggered rules | READY |

### Key invariants enforced
- **UNKNOWN ≠ READY** — explicitly prevented; UNKNOWN has higher precedence than AT_RISK
- All 4 inputs may be `None` / missing — triggers R8 (UNKNOWN)
- Deterministic: identical inputs always produce identical outputs
- No LLM in any part of the decision

### Tests: `src/backend/tests/ml/test_readiness_engine.py`
**128 tests** across 13 test classes:
- Per-rule tests (R1–R12 each individually triggered)
- Precedence: NOT_READY beats UNKNOWN beats AT_RISK beats READY
- Contradictory conditions (conflicting signals — highest-severity wins)
- UNKNOWN ≠ READY enforcement
- Determinism across multiple calls
- Custom threshold overrides
- Confidence scoring
- 14 specification edge cases
- Evidence quality scoring
- Boundary values (exactly at threshold, one epsilon above/below)

---

## Phase 8 — Mission Engine

### Package: `src/backend/app/ml/mission/`

| Module | Responsibility |
|---|---|
| `__init__.py` | Package exports |
| `models.py` | `MissionInput`, `MissionOutput`, `CapabilityRequirement`, `AssetCapability`, `ReadinessGap`, `SubstitutionCandidate`, `ConflictReport`, `MissionRiskLevel`, `MissionStatus` (GO/GO_WITH_RISK/NO_GO/UNKNOWN) |
| `engine.py` | `MissionEngine.evaluate()` — pure deterministic evaluation |

### Logic
1. Check all assigned assets against each capability requirement
2. Detect shortages (not enough READY assets per capability)
3. Search fleet for substitution candidates (ranked by fitness score)
4. Detect conflicts (asset assigned to multiple concurrent missions)
5. Compute `risk_score` ∈ [0, 1] from gap severity × criticality weights
6. Determine verdict: GO / GO_WITH_RISK / NO_GO / UNKNOWN
   - UNKNOWN if no assignments and no fleet data
   - NO_GO if any critical capability gap has shortage > 0
   - GO_WITH_RISK if non-critical gaps or risk_score > 0.4
   - GO otherwise

---

## Phase 9 — Maintenance Prioritizer

### Package: `src/backend/app/ml/maintenance/`

| Module | Responsibility |
|---|---|
| `__init__.py` | Package exports |
| `models.py` | `MaintenanceItem`, `PrioritizedItem`, `MaintenanceQueue`, `UrgencyLevel` (IMMEDIATE/URGENT/SCHEDULED/ROUTINE/DEFERRED), `AssetCriticality`, `ComponentCriticality`, `SafetyClassification` |
| `prioritizer.py` | `MaintenancePrioritizer.prioritize()` — weighted scoring formula |

### Weighted formula

| Factor | Weight |
|---|---|
| Failure risk | 30% |
| RUL urgency | 20% |
| Mission proximity | 20% |
| Asset criticality | 10% |
| Component criticality | 10% |
| Safety classification | 5% |
| Overdue penalty | 5% |

- Safety override: safety-critical items cannot be DEFERRED regardless of score
- Items blocking an upcoming mission are flagged `blocks_mission = True`
- Urgency thresholds: IMMEDIATE ≥ 0.8, URGENT ≥ 0.6, SCHEDULED ≥ 0.4, ROUTINE ≥ 0.2, else DEFERRED

---

## Phase 10 — Backend API

### ORM Models

| File | Models |
|---|---|
| `src/backend/app/models/fleet.py` | `Asset`, `Component`, `Sensor` |
| `src/backend/app/models/telemetry.py` | `Telemetry`, `Prediction`, `DataQualityEvent` |
| `src/backend/app/models/operations.py` | `Mission`, `MissionRequirement`, `MissionAssignment`, `WorkOrder`, `Alert`, `AssetReadiness` |
| `src/backend/app/core/audit.py` | `AuditLog` |

All models imported in `migrations/env.py` for Alembic autogenerate.

### Repositories

| File | Repositories |
|---|---|
| `src/backend/app/repositories/fleet_repository.py` | `AssetRepository`, `ComponentRepository`, `SensorRepository` |
| `src/backend/app/repositories/operations_repository.py` | `MissionRepository`, `WorkOrderRepository`, `AlertRepository`, `ReadinessRepository`, `PredictionRepository`, `DataQualityRepository` |

### Schemas

| File | Schemas |
|---|---|
| `src/backend/app/schemas/fleet.py` | `AssetBase/Create/Update/Response`, `ComponentCreate/Response`, `SensorCreate/Response` |
| `src/backend/app/schemas/operations.py` | `Mission*`, `WorkOrder*`, `Alert*`, `Readiness*`, `Prediction*`, `DataQualityEvent*` |

### API Routes (all under `/api/v1`)

| Route file | Prefix | Key endpoints |
|---|---|---|
| `assets.py` | `/assets` | CRUD + `/components`, `/sensors`, `/predictions`, `/readiness`, `/alerts` |
| `missions.py` | `/missions` | CRUD + `/assignments`, `/{id}/readiness` (MissionEngine) |
| `maintenance.py` | `/maintenance` | `/work-orders` CRUD + `/queue` (MaintenancePrioritizer) |
| `alerts.py` | `/alerts` | List + `/{id}/acknowledge` |
| `readiness.py` | `/readiness` | Fleet summary + `/evaluate/{asset_id}` + `/all` |
| `data_quality.py` | `/data-quality` | Events list (severity/type filters) + `/summary` |
| `copilot.py` | `/copilot` | `POST /query` |

### Services

| File | Responsibility |
|---|---|
| `src/backend/app/services/readiness_service.py` | Bridges `ReadinessEngine` to DB — loads asset data, invokes engine, persists `AssetReadiness` record |
| `src/backend/app/services/copilot_service.py` | Intent detection → 7 backend tool calls → grounded context → `ibm/granite-13b-instruct-v2` via watsonx.ai; graceful degradation when credentials absent |

---

## Phase 11 — Frontend UI

All pages use `NavBar` (shared component), `'use client'` first line, all data from API — no hardcoded values.

### Shared component: `src/frontend/components/NavBar.jsx`
- 7 nav links: Dashboard / Assets / Missions / Maintenance / Alerts / Data Quality / Copilot
- Active-link highlight via `usePathname()`
- API status pill (ONLINE / OFFLINE / checking)
- User name + role display
- Logout button
- Mobile hamburger dropdown

### Pages

| Page | Path | Features |
|---|---|---|
| Dashboard | `app/dashboard/page.jsx` | Fleet readiness summary, stat cards, asset readiness grid, active alerts |
| Assets list | `app/assets/page.jsx` | Search + status filter, readiness-enriched cards |
| Asset detail | `app/assets/[assetId]/page.jsx` | Readiness card, predictions chart, components, sensors, alerts; re-evaluate button |
| Missions list | `app/missions/page.jsx` | Mission cards + `CreateMissionModal` (code, name, priority, dates, capability requirements) |
| Mission detail | `app/missions/[missionId]/page.jsx` | Header + status transition buttons, requirements chips, `ReadinessPanel` (capability status, gaps + substitutions, conflicts), `AssignAssetModal`, re-evaluate |
| Maintenance | `app/maintenance/page.jsx` | Priority Queue tab (score breakdown per item) + Work Orders tab; `CreateWorkOrderModal` (asset picker, urgency, blocking flag) |
| Alerts | `app/alerts/page.jsx` | Severity/status filters, acknowledge button |
| Data Quality | `app/data-quality/page.jsx` | 6-counter summary row, severity + issue-type filters, paginated event list with asset/sensor enrichment |
| Copilot | `app/copilot/page.jsx` | Chat UI, asset-code context field, evidence expandable panel, suggested queries, grounding disclaimer banner |

---

## Phase 12 — watsonx.ai Copilot

### `src/backend/app/services/copilot_service.py`

**Architecture:** intent detection → backend tool calls → grounded context string → LLM explains only

**7 backend tools:**
1. `fleet_readiness_summary` — overall fleet status counts
2. `asset_readiness_detail` — single asset readiness + reason codes
3. `active_alerts` — active/critical alerts list
4. `maintenance_queue` — top prioritized maintenance items
5. `mission_status` — list missions with their statuses
6. `asset_details` — asset metadata + recent predictions
7. `data_quality_summary` — unresolved DQ event counts

**Model:** `ibm/granite-13b-instruct-v2` via `ibm-watsonx-ai` SDK  
**Graceful degradation:** if `WATSONX_API_KEY` / `WATSONX_PROJECT_ID` absent, returns structured evidence without LLM narrative  
**Principle:** LLM never decides readiness — it only narrates retrieved evidence

---

## Phase 13 — Security / RBAC

### `src/backend/app/core/audit.py`
- `AuditLog` ORM model: `id`, `user_id`, `action`, `resource_type`, `resource_id`, `details` (JSON), `ip_address`, `created_at`
- `AuditLogger` service: `log(db, user_id, action, resource_type, resource_id, details)`

### RBAC enforcement
- `require_roles(*roles)` from `app.api.deps` applied on all write endpoints
- Role constants: `OPERATOR`, `MAINTAINER`, `ADMIN` from `app.core.roles`
- Assets `POST`/`PATCH` require `MAINTAINER` or `ADMIN`
- Audit log entries written on `asset.create` and `asset.update`

---

## Test Results

```
133 passed in 39.40s
  - tests/test_health.py             5 tests
  - tests/ml/test_readiness_engine.py  128 tests
  - tests/ml/test_simulator.py       (28 tests — passing from BOB-005)
```

---

## Import Path Convention (frontend)

All `app/<page>/page.jsx` files (depth-2):
- `../../lib/api`
- `../../components/NavBar`

All `app/<page>/[param]/page.jsx` files (depth-3):
- `../../../lib/api`
- `../../../components/NavBar`

---

## Files Created

### Backend — ML engines
- `src/backend/app/ml/readiness/__init__.py`
- `src/backend/app/ml/readiness/models.py`
- `src/backend/app/ml/readiness/engine.py`
- `src/backend/app/ml/mission/__init__.py`
- `src/backend/app/ml/mission/models.py`
- `src/backend/app/ml/mission/engine.py`
- `src/backend/app/ml/maintenance/__init__.py`
- `src/backend/app/ml/maintenance/models.py`
- `src/backend/app/ml/maintenance/prioritizer.py`

### Backend — ORM models
- `src/backend/app/models/fleet.py`
- `src/backend/app/models/telemetry.py`
- `src/backend/app/models/operations.py`
- `src/backend/app/core/audit.py`

### Backend — Repositories
- `src/backend/app/repositories/fleet_repository.py`
- `src/backend/app/repositories/operations_repository.py`

### Backend — Schemas
- `src/backend/app/schemas/fleet.py`
- `src/backend/app/schemas/operations.py`

### Backend — Services
- `src/backend/app/services/readiness_service.py`
- `src/backend/app/services/copilot_service.py`

### Backend — API routes
- `src/backend/app/api/routes/assets.py`
- `src/backend/app/api/routes/missions.py`
- `src/backend/app/api/routes/maintenance.py`
- `src/backend/app/api/routes/alerts.py`
- `src/backend/app/api/routes/readiness.py`
- `src/backend/app/api/routes/data_quality.py`
- `src/backend/app/api/routes/copilot.py`

### Backend — Tests
- `src/backend/tests/ml/test_readiness_engine.py`

### Frontend — New pages
- `src/frontend/app/missions/[missionId]/page.jsx`
- `src/frontend/app/data-quality/page.jsx`

### Frontend — Shared component
- `src/frontend/components/NavBar.jsx`

---

## Files Modified

### Backend
- `src/backend/app/main.py` — registered all 8 routers
- `src/backend/app/core/database.py` — `create_tables()` imports all models
- `src/backend/app/models/__init__.py` — exports all 13 ORM models
- `src/backend/migrations/env.py` — imports all model modules for Alembic autogenerate
- `src/backend/app/api/routes/data_quality.py` — severity/type filters, enriched response (asset_code, sensor_code, issue_type, created_at aliases), richer summary
- `src/backend/app/repositories/operations_repository.py` — `DataQualityRepository.list()` accepts `severity` and `event_type` filters
- `src/backend/app/ml/validation/schema.py` — fixed `SAMPLING_RATE_HZ` → `_IMS_SAMPLING_RATE_HZ = 20_000.0`

### Frontend
- `src/frontend/lib/api.js` — added all API functions: assets, readiness, missions, maintenance, alerts, data-quality, copilot
- `src/frontend/app/dashboard/page.jsx` — NavBar, live data
- `src/frontend/app/assets/page.jsx` — NavBar, live data
- `src/frontend/app/assets/[assetId]/page.jsx` — NavBar, full drill-down
- `src/frontend/app/missions/page.jsx` — NavBar + CreateMissionModal
- `src/frontend/app/maintenance/page.jsx` — NavBar + CreateWorkOrderModal
- `src/frontend/app/alerts/page.jsx` — NavBar
- `src/frontend/app/copilot/page.jsx` — NavBar, asset-code input moved to bottom bar
