# BOB-005 — Phase 4: Synthetic Digital Fleet Simulator

**Session:** BOB-005  
**Phase:** 4 (Phase 5 in IMPLEMENTATION_PLAN.md numbering)  
**Date:** 2025  
**Status:** ✅ COMPLETE — all gate criteria passed

---

## Objective

Build a controlled, reproducible synthetic fleet simulator that generates realistic HUMS telemetry from first principles, with strict anti-leakage separation between truth and observable data.

---

## Implemented

### Package: `src/backend/app/ml/simulator/`

| Module | Responsibility |
|---|---|
| `config.py` | `SimulatorConfig`, `FleetProfile`, asset/component/sensor specs, `DegradationParams`, `MaintenanceParams`, `MissionParams`, `EdgeCaseParams`, YAML loader |
| `rng.py` | `RNGManager` — deterministic per-entity RNG via SHA-256 child seeds |
| `degradation.py` | 6 archetypes: HEALTHY, GRADUAL, ACCELERATED, ABRUPT, NONLINEAR, RECOVERABLE; `compute_true_rul()` |
| `environment.py` | 5 operating conditions; per-sensor baseline offsets; `ConditionSchedule` |
| `truth.py` | `ComponentTruth`, `AssetTruth`, `FleetTruth` — latent ground truth (never exported to observable) |
| `sensor.py` | Ideal signal → noise → fault application pipeline; `SensorFaultType` enum |
| `maintenance.py` | Scheduled / corrective / replacement maintenance; health recovery curves |
| `mission.py` | Mission scheduling with conflict detection |
| `edge_cases.py` | `EdgeCasePlanner` — assigns 15 edge case types to assets before simulation |
| `assembly.py` | Fleet factory — deterministic UUIDs from RNG; 3 asset types, 2–3 components, 2–3 sensors |
| `engine.py` | `FleetSimulator` — main per-asset simulation loop (causal chain) |
| `export.py` | `SimulationResult` — anti-leakage observable/truth split; `FORBIDDEN_OBSERVABLE_COLUMNS` guard |
| `validate.py` | 9-check validation suite |

### Profiles: `src/backend/data/simulator/profiles/`
- `tiny.yaml` — 10 assets, 365 days, seed=42
- `validation.yaml` — 100 assets, 730 days, seed=123
- `demo.yaml` — 1000 assets config (not generated — requires explicit request)

### Tests: `src/backend/tests/ml/test_simulator.py`
28 tests covering: determinism, leakage, degradation monotonicity, failure precedence, maintenance recovery, all 15 edge case types, performance (<60s tiny), referential integrity, timestamp monotonicity, mission conflict, censored assets.

---

## Causal Chain

```
latent true state (ComponentTruth.health)
    ↓  step_health() — archetype × condition_mult × degradation_multiplier
    ↓  ideal physical signal — compute_ideal_signal() 
    ↓  operating condition baseline offset
    ↓  sensor noise — add_sensor_noise()
    ↓  fault application — apply_fault() (MISSING/STALE/STUCK/OUTLIER/DRIFT/DUPLICATE/FAILURE)
    ↓  observed telemetry row (no health, no RUL, no failure timestamp)
```

---

## Tiny Profile Results (10 assets, 365 days, seed=42)

| Metric | Value |
|---|---|
| Runtime | 5.5s |
| Assets | 10 (4 HELICOPTER, 3 FIXED_WING, 3 GROUND_VEHICLE) |
| Components | 25 |
| Sensors | 59 |
| Telemetry rows | 413,414 |
| DQ events | 16,746 |
| Maintenance events | 376 (241 corrective, 112 replacement, 23 scheduled) |
| Missions | 88 (1 conflict) |
| Failures | 1 component |
| Validation | 9/9 checks PASSED |

### Edge cases injected

| Asset | Tags |
|---|---|
| FW-003 | missing_telemetry |
| AH-002 | duplicate_timestamp, mission_conflict, rul_shorter_than_mission, component_degradation, stale_telemetry |
| AH-004 | sensor_failure, poor_quality_genuine_degradation, high_anomaly_low_failure, stuck_sensor |
| FW-004 | outlier |
| GV-001 | overdue_maintenance, drift |
| FW-002 | insufficient_data |

---

## Validation Profile Results (100 assets, 730 days, seed=123)

| Metric | Value |
|---|---|
| Runtime | 129s |
| Assets | 100 (41 HELICOPTER, 34 FIXED_WING, 25 GROUND_VEHICLE) |
| Components | 241 |
| Sensors | 557 |
| Telemetry rows | 9,371,918 |
| DQ events | 33,480 |
| Maintenance events | 5,364 |
| Missions | 2,799 |
| Failure events | 6 components |
| Health distribution | 6 failed / 78 degraded / 81 at-risk / 76 healthy |
| Validation | 9/9 checks PASSED |

---

## Anti-Leakage Safeguards

**Forbidden in observable tables:**
`true_health`, `true_rul`, `failure_timestamp`, `latent_health`, `degradation_multiplier`, `archetype`, `failure_type`, `health`

**Enforcement layers:**
1. `engine.py` never writes health values to `tel_rows`, `dq_rows`, `maint_rows`, or `mission_rows`.
2. `export.py::build_result()` explicitly drops any forbidden column that leaks through.
3. `SimulationResult.validate_no_leakage()` programmatically checks all observable tables.
4. `test_no_leakage_in_observable` test in the test suite.
5. `_check_leakage` in validation suite.

---

## Known Limitations

1. **Degradation rates not calibrated against real data yet** — C-MAPSS and IMS are referenced architecturally (GRADUAL ≈ C-MAPSS piecewise linear; NONLINEAR ≈ IMS kurtosis spike) but not quantitatively fitted. Phase 6 will close this gap.
2. **1,000-asset dataset not generated** — config exists; generation takes ~20+ min and creates ~30M rows.
3. **No PostgreSQL ingestion yet** — simulator outputs in-memory DataFrames; DB write deferred pending Alembic migrations (Phase 3 of DB plan).
4. **Health-dip recovery edge case (HIGH_ANOMALY_LOW_FAILURE)** causes slight non-monotonicity that the validation suite accommodates with median-based comparison.
5. **Stale/MISSING fault durations** are fixed at injection time — a production implementation would use a Markov fault model for more realistic intermittent failures.
6. **`under_maintenance` edge case** is not independently tagged — it manifests as MAINTENANCE_GROUND operating condition in telemetry which is the correct observable signal.

---

## Files Created / Modified

**New:**
- `src/backend/app/ml/simulator/__init__.py`
- `src/backend/app/ml/simulator/config.py`
- `src/backend/app/ml/simulator/rng.py`
- `src/backend/app/ml/simulator/degradation.py`
- `src/backend/app/ml/simulator/environment.py`
- `src/backend/app/ml/simulator/truth.py`
- `src/backend/app/ml/simulator/sensor.py`
- `src/backend/app/ml/simulator/maintenance.py`
- `src/backend/app/ml/simulator/mission.py`
- `src/backend/app/ml/simulator/edge_cases.py`
- `src/backend/app/ml/simulator/assembly.py`
- `src/backend/app/ml/simulator/engine.py`
- `src/backend/app/ml/simulator/export.py`
- `src/backend/app/ml/simulator/validate.py`
- `src/backend/data/simulator/profiles/tiny.yaml`
- `src/backend/data/simulator/profiles/validation.yaml`
- `src/backend/data/simulator/profiles/demo.yaml`
- `src/backend/tests/ml/test_simulator.py`

**Modified:**
- `docs/IMPLEMENTATION_PLAN.md` — Phase 5 marked complete
- `AGENTS.md` — updated (separate session)
