# IMPLEMENTATION_PLAN.md — MissionReady AI

## Overview

This document is the authoritative phase-by-phase implementation roadmap. No phase begins until the preceding phase has passed its gate criteria. No placeholder functionality silently continues.

---

## Phase Gates

Every phase must satisfy ALL of the following before the next phase begins:

- [ ] Implementation complete
- [ ] Tests written and passing
- [ ] Architecture/documentation updated to reflect what was built
- [ ] Known issues documented
- [ ] Acceptance criteria verified

---

## PHASE 1 — Research & Architecture ✅ COMPLETE

**Objective:** Understand the full scope, design the system, and produce all planning documents.

**Deliverables:**
- [x] `docs/RESEARCH.md`
- [x] `docs/ARCHITECTURE.md`
- [x] `docs/PERSONAS.md`
- [x] `docs/KPIS.md`
- [x] `docs/DATA_MODEL.md`
- [x] `docs/API.md`
- [x] `docs/SECURITY.md`
- [x] `docs/IMPLEMENTATION_PLAN.md`
- [x] `docs/BOB_USAGE.md`

**Gate Criteria:**
- All documents internally consistent
- No unanswered blocking questions
- Stack decisions confirmed

**STOP. No application code until Phase 2.**

---

## PHASE 2 — Project Scaffolding ✅ COMPLETE

**Objective:** Working skeleton. Every service starts. Health endpoint passes. Test infrastructure exists.

**Tasks:**

Backend:
1. Add Alembic to `requirements.txt`; initialise `src/backend/migrations/`
2. Add ML dependencies to `src/backend/requirements-ml.txt` (numpy, pandas, scipy, scikit-learn, xgboost, lightgbm)
3. Add `slowapi` (rate limiting) to `requirements.txt`
4. Set up `pytest` configuration in `src/backend/pyproject.toml`
5. Create `src/backend/tests/conftest.py` with test database fixture
6. Verify `uvicorn app.main:app --reload` starts from `src/backend/`
7. Write smoke test: `GET /health` returns 200

Frontend:
8. Add TanStack Query (`@tanstack/react-query`)
9. Add Recharts
10. Create `src/frontend/types/` directory for TypeScript types (new modules)
11. Verify `npm run dev` starts from `src/frontend/`

Infrastructure:
12. Create `docker-compose.yml` at repo root with PostgreSQL 15 and backend service
13. Document local setup in `docs/setup-guide.md` (real content)

**Gate Criteria: ALL PASSED**
- ✅ `GET /health` returns standard envelope `{success, data, meta, error}` with running backend
- ✅ `npm run dev` starts without errors (Vite dev server on port 5173)
- ✅ `docker-compose.yml` written; `docker compose up db -d` starts PostgreSQL (requires Docker)
- ✅ `pytest` — 5/5 tests passing, 0 warnings
- ✅ TypeScript typecheck — 0 errors; production build — 0 errors

**Notes:**
- Frontend migrated to Vite + React 19 + TypeScript 6 per user instruction (not Next.js 14).
- Active frontend is `src/frontend-new/`; legacy Next.js `src/frontend/` preserved.
- Alembic initialised; `alembic upgrade head` ready for Phase 3 migrations.

---

## PHASE 3 — Database Foundation ✅ COMPLETE

**Objective:** All tables created via Alembic migrations. CRUD verified. Test data seeded.

**Tasks:**

1. Write Alembic initial migration creating all tables in `docs/DATA_MODEL.md`
   - Priority order: users → assets → components → sensors → telemetry → predictions → missions → work_orders → alerts → copilot tables → audit_logs
2. Apply migration: `alembic upgrade head`
3. Verify all tables exist with correct columns, indexes, and foreign keys
4. Create minimal seed script: 3 assets, 2 components each, 2 sensors each, 1 mission — **`scripts/seed_demo_data.py`**
5. Write CRUD integration tests for: assets, components, work_orders
6. Update `docs/setup-guide.md` with migration commands

**Gate Criteria:**
- `alembic upgrade head` completes without errors on clean database
- `alembic downgrade base` and `alembic upgrade head` round-trips correctly
- All repository-layer tests pass
- Seeded data is queryable

---

## PHASE 4 — Data Ingestion (External Datasets)

**Objective:** NASA C-MAPSS and IMS datasets downloaded, documented, and preprocessed. Feature shapes verified. No ML training yet.

**Tasks:**

1. Create `docs/DATA_PROVENANCE.md`
2. Download NASA C-MAPSS (FD001–FD004) to `src/backend/data/raw/cmapss/`
3. Download NASA IMS Bearings to `src/backend/data/raw/ims/`
4. Write preprocessing pipeline for C-MAPSS:
   - Parse train/test/RUL files
   - Add column names (sensor_1..sensor_21, setting_1..setting_3)
   - Compute piecewise-linear RUL labels
   - Extract rolling window features (mean, std, trend) with configurable window
   - Output: `data/processed/cmapss_features.parquet`
5. Write preprocessing pipeline for IMS:
   - Parse bearing vibration CSV files
   - Extract time-domain features (RMS, kurtosis, crest factor, peak)
   - Extract frequency-domain features (spectral centroid, band energy)
   - Output: `data/processed/ims_features.parquet`
6. Write leakage detection tests: verify `true_rul`, `true_health`, `failure_events` are not in feature columns
7. Write distribution tests: verify feature value ranges are physically plausible

**Gate Criteria:**
- Both datasets downloadable with documented provenance
- Feature DataFrames have correct shapes and no NaN in expected columns
- Leakage tests pass
- Distribution sanity tests pass

---

## PHASE 5 — Synthetic Data Generator ✅ COMPLETE (implemented as Phase 4)

**Objective:** Causal digital-fleet simulator producing realistic HUMS telemetry. Validated at 10 → 100 assets.

**Deliverables:**
- [x] `src/backend/app/ml/simulator/` — full simulator package (config, rng, degradation, environment, truth, sensor, maintenance, mission, edge_cases, assembly, engine, export, validate)
- [x] `src/backend/data/simulator/profiles/` — tiny.yaml, validation.yaml, demo.yaml
- [x] `src/backend/tests/ml/test_simulator.py` — 28 tests, all passing

**Gate Criteria: ALL PASSED**
- ✅ Simulator produces deterministic output with fixed seed (test_deterministic_output)
- ✅ 9/9 validation checks pass on tiny (10 assets, 365 days) profile
- ✅ 9/9 validation checks pass on validation (100 assets, 730 days) profile
- ✅ No ground-truth leakage columns in observable tables (test_no_leakage_in_observable)
- ✅ All 14+ edge case types injected and detected
- ✅ 28/28 tests passing in ~21s

**Notes:**
- 1,000-asset demo profile config exists (demo.yaml) but dataset not generated — requires explicit request.
- Database ingestion deferred to Phase 5 (DB migrations not yet applied).
- Session evidence: `bob_sessions/BOB-005-phase4-simulator.md`

---

## PHASE 6 — ML Baseline: RUL Model ✅ IMPLEMENTED (training pipeline ready)

**Objective:** Trained, evaluated, and versioned RUL regression model.

**Tasks:**

1. Build feature engineering pipeline:
   - Rolling window statistics (mean, std, min, max, trend slope)
   - Operating condition normalisation
   - Vibration features from IMS pipeline
   - Maintenance age feature (hours since last overhaul per component)
2. Asset-level train/validation/holdout split (never row-level)
3. Train baseline model: `GradientBoostingRegressor` or XGBoost
4. Evaluate on validation set: MAE, RMSE, R²
5. Evaluate on C-MAPSS holdout test set (official test split)
6. Plot learning curves; document whether more data improves validation performance
7. Calibrate confidence bounds (prediction intervals)
8. Register model in `model_versions` table
9. Store metrics in `model_metrics` table
10. Write leakage test: confirm `true_rul`, `true_health`, `failure_events` not in feature set
11. Write prediction sanity tests: RUL never negative, confidence always > 0

**Gate Criteria:**
- MAE on validation set documented
- RUL predictions are non-negative
- Leakage tests pass
- Model version registered in DB

---

## PHASE 7 — Failure Risk Model ✅ IMPLEMENTED (training pipeline ready)

**Objective:** Trained, evaluated, calibrated failure risk classifier.

**Tasks:**

1. Define binary target: failure within 24h / 72h / mission window
2. Handle class imbalance (failure events are rare): use balanced class weights or oversampling
3. Train gradient boosting classifier
4. Evaluate: Precision, Recall, F1, PR-AUC (preferred over ROC-AUC for imbalanced)
5. Calibrate probabilities (Platt scaling)
6. Verify false negative rate (missed failures) is acceptable
7. Register in `model_versions` + `model_metrics`
8. Write prediction sanity tests: probability always in [0, 1]

**Gate Criteria:**
- PR-AUC documented and acceptable for demo
- Calibration error (ECE) computed
- False positive and false negative rates documented

---

## PHASE 8 — Anomaly Model ✅ IMPLEMENTED (training pipeline ready)

**Objective:** Trained anomaly detector producing interpretable scores.

**Tasks:**

1. Train `IsolationForest` per-asset (or per-component-type)
2. Score all synthetic telemetry windows
3. Evaluate on known data quality injection events: anomaly scores should be elevated on injected faults
4. Extract top contributing sensors per anomalous reading (feature permutation or contrastive)
5. Register in `model_versions` + `model_metrics`

**Gate Criteria:**
- Known injected anomalies score above threshold
- Contributing sensor attribution works for at least 80% of anomalous readings

---

## PHASE 9 — Readiness Engine ✅ COMPLETE

**Objective:** Deterministic, tested, explainable readiness classification.

**Tasks:**

1. Implement `ReadinessEngine` service with rules as defined in `docs/ARCHITECTURE.md`
2. Implement configurable thresholds (failure_probability cutoff, RUL safety margin, stale threshold)
3. Attach `reason_code` and `contributing_factors` to every readiness output
4. Implement mission-level readiness aggregation
5. Test all 14 edge cases from spec §18:
   - Missing telemetry → UNKNOWN
   - Stale sensor → UNKNOWN or AT_RISK per policy
   - Outlier (not actual failure) → anomaly elevated but not automatic NOT_READY
   - Sensor drift → AT_RISK
   - Duplicate timestamp → handled gracefully
   - Asset under maintenance → NOT_READY
   - RUL below mission duration → NOT_READY
   - High anomaly + low failure risk → AT_RISK, investigate (not auto NOT_READY)
   - High failure risk + poor data quality → lower confidence, NOT_READY
   - Maintenance recovery → readiness re-evaluated after work order completion
   - Right-censored asset → UNKNOWN if no valid prediction
   - Mission conflict → NOT_READY
   - Overdue maintenance → AT_RISK or NOT_READY per criticality
   - Sensor failure vs component failure → distinguish in reason_code

**Gate Criteria:**
- All 14 edge case tests pass
- Readiness output is deterministic (same inputs → same output)
- No readiness change without a logged `reason_code`

---

## PHASE 10 — Maintenance Prioritisation ✅ COMPLETE

**Objective:** Transparent, tested maintenance scoring and recommendation engine.

**Tasks:**

1. Implement priority score formula from `docs/KPIS.md`
2. Generate work orders from predictions above threshold
3. Attach evidence (contributing factors) to every recommendation
4. Implement "blocks_mission" flag logic
5. Implement urgency escalation when mission proximity decreases
6. Write tests: verify ordering is correct for known scenarios

**Gate Criteria:**
- Prioritisation is deterministic and transparent
- Every work order has evidence attached
- Priority ordering tests pass

---

## PHASE 11 — AI Copilot ✅ COMPLETE

**Objective:** Grounded copilot answering natural-language queries backed by real backend data.

**Tasks:**

1. Implement `CopilotService` with backend tool framework:
   - `get_fleet_summary()`
   - `get_asset_status(asset_code)`
   - `get_asset_prediction(asset_code)`
   - `get_maintenance_recommendations(asset_code)`
   - `get_mission_readiness(mission_code)`
   - `get_data_quality_summary()`
2. Implement intent detection (keyword routing or small classifier)
3. Build grounded context string from tool results
4. Integrate watsonx.ai SDK (`ibm-watsonx-ai`) with:
   - API key from server-side env only
   - Approved model (granite or equivalent)
   - Prompt template that instructs the model to use only provided context
5. Log all tool calls to `copilot_messages` + `copilot_evidence`
6. Write tests:
   - Tool calls produce correct structured data
   - AI does not invent data not in context (test with known-empty context)
   - Role-restricted tools refuse unauthorised callers

**Gate Criteria:**
- Copilot answers "Why is {asset} at risk?" with evidence from actual DB
- No hallucinated telemetry values in responses
- All tool calls logged

---

## PHASE 12 — Frontend ✅ COMPLETE

**Objective:** All routes implemented and connected to live backend data. No mock/placeholder data.

**Sub-phases (each must pass individually):**

### 12a — Protected Routing & Auth Context
- TanStack Query setup, `AuthProvider` context
- Route guard: redirect to `/login` if no valid token
- Fetch `/auth/me` on startup to validate token

### 12b — Dashboard (`/dashboard`)
- Fleet KPI cards (ready, at-risk, not-ready, unknown)
- Next mission banner
- Critical alerts list
- Maintenance urgency summary
- Data freshness indicator

### 12c — Assets (`/assets`)
- Filterable, sortable asset table with readiness status badges
- Search by asset code / call sign

### 12d — Asset Detail (`/assets/:assetId`)
- Readiness status with reason
- Per-component health indicators
- RUL with confidence bands
- Failure probability
- Telemetry time-series charts (Recharts)
- Anomaly score overlay
- Explanation section (contributing factors)
- Maintenance history

### 12e — Missions (`/missions` + `/missions/:missionId`)
- Mission list with readiness summary
- Per-mission asset breakdown
- Substitution recommendations

### 12f — Maintenance (`/maintenance` + `/maintenance/:workOrderId`)
- Priority-sorted work order queue
- Work order detail with evidence
- Create/update work order forms

### 12g — Alerts (`/alerts`)
- Alert list filtered by status/severity
- Acknowledge action

### 12h — Data Quality (`/data-quality`)
- Quality score KPIs
- Event list with affected sensors

### 12i — Copilot (`/copilot`)
- Chat interface
- Evidence panel showing sources

### 12j — Models (`/models`)
- Model version list and metrics (restricted to engineer/admin roles)

**Gate Criteria per sub-phase:** Connected to real backend, no hardcoded/mock data, tests exist.

---

## PHASE 13 — Security Hardening ✅ COMPLETE

1. Run `pip audit` on backend dependencies
2. Run `npm audit` on frontend dependencies
3. Run `bandit` static analysis on backend Python
4. Add security headers middleware
5. Add rate limiting (`slowapi`)
6. Audit all routes for missing role checks
7. Audit all response schemas for sensitive field exposure
8. Review all copilot tool call logs for data leakage
9. Pin all package versions
10. Validate CORS configuration is not overly permissive

---

## PHASE 14 — End-to-End Testing

**Target workflow:**

1. Login → Dashboard → see fleet KPIs
2. Click AT_RISK asset → Asset Detail → see telemetry + prediction
3. Open prediction explanation → see contributing factors
4. Check mission readiness → see gap
5. Open maintenance queue → see priority order
6. Create a work order → verify it appears in queue
7. Acknowledge an alert
8. Ask copilot "Why is {asset} at risk?" → see grounded answer with evidence
9. View data quality dashboard
10. View model metrics page

---

## PHASE 15 — Polish

- Loading states on all async operations
- Empty states (no assets, no alerts, no missions)
- Error boundaries and error states
- Responsive behaviour (tablet minimum)
- Accessibility audit (labels, ARIA, keyboard navigation)
- Performance: dashboard loads in under 3 seconds on local network

---

## PHASE 16 — Submission

- [ ] Update `docs/setup-guide.md` with exact run commands
- [ ] Update `docs/architecture.md` (hackathon template version) with final architecture
- [ ] Update `docs/problem-statement.md` with real content
- [ ] Update `docs/solution-overview.md` with real content
- [ ] Verify `demo/demo-video-link.txt` has real URL
- [ ] Add screenshots to `demo/screenshots/`
- [ ] Add `presentation/slides.pdf`
- [ ] Run full test suite — 0 failures
- [ ] Run GitHub Actions validate workflow — green
- [ ] Verify no secrets in git: `git log --all -p | grep -i "api_key\|secret\|password"` returns nothing sensitive
- [ ] Export Bob session evidence to `bob_sessions/`
- [ ] Repository is public

---

## Dependency Installation Plan

### Backend (to be added in Phase 2):

```bash
# requirements.txt additions
alembic==1.14.0
slowapi==0.1.9

# requirements-ml.txt (new file)
numpy==2.2.0
pandas==2.2.3
scipy==1.14.1
scikit-learn==1.6.0
xgboost==2.1.2
lightgbm==4.5.0
ibm-watsonx-ai==1.1.15
```

### Frontend (to be added in Phase 2):

```bash
npm install @tanstack/react-query recharts
```

---

## Unresolved Questions

| Question | Impact | Resolution Target |
|---|---|---|
| Is a local PostgreSQL (Docker) available, or will a cloud DB (Neon/Supabase) be used? | Phase 2 | Before Phase 2 begins |
| Which watsonx.ai model is approved for this hackathon? | Phase 11 | Before Phase 11 begins |
| Is `WATSONX_API_KEY` already available in the team's `.env`? | Phase 11 | Confirm before Phase 11 |
| Should the frontend remain `.jsx` or migrate to TypeScript? | Phase 12 | New modules use `.tsx`; existing `.jsx` files are not renamed |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| PostgreSQL not available locally | High | High | Use Docker Compose (include in Phase 2) or Neon free tier |
| watsonx.ai credentials not available | Medium | High | Build copilot with stub LLM first; swap in real model when credentials confirmed |
| NASA dataset download fails | Low | Medium | Cache datasets; document manual download steps |
| ML model performance insufficient for demo | Medium | Medium | Prioritise explainability over accuracy; use placeholder predictions backed by simulator ground truth if needed |
| Phase timeline runs out before Phase 16 | High | High | Cut polish (Phase 15) before cutting functionality; never cut security or testing |
