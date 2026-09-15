# KPIS.md — MissionReady AI

## Overview

This document defines all Key Performance Indicators tracked and displayed by MissionReady AI. Every KPI must have a clear source table, calculation method, and display location.

---

## 1. Fleet KPIs

These appear on the `/dashboard` and `/assets` pages.

| KPI | Description | Source | Calculation |
|---|---|---|---|
| `total_assets` | Total assets in the fleet | `assets` | `COUNT(*)` where `is_active = true` |
| `ready_count` | Assets with READY status | `predictions` latest per asset | readiness_engine output = 'READY' |
| `at_risk_count` | Assets with AT_RISK status | `predictions` latest per asset | readiness_engine output = 'AT_RISK' |
| `not_ready_count` | Assets with NOT_READY status | `predictions` latest per asset | readiness_engine output = 'NOT_READY' |
| `unknown_count` | Assets with UNKNOWN status | `predictions` latest per asset | readiness_engine output = 'UNKNOWN' |
| `readiness_pct` | % of active assets that are READY | calculated | `ready_count / total_assets * 100` |
| `at_risk_pct` | % of active assets that are AT_RISK | calculated | `at_risk_count / total_assets * 100` |

**Threshold Guidance (configurable):**
- Readiness < 70% → dashboard warning state
- Readiness < 50% → dashboard critical state

---

## 2. Prediction KPIs

Displayed on asset detail pages and in copilot responses.

| KPI | Description | Unit | Null Behaviour |
|---|---|---|---|
| `rul_estimate` | Predicted remaining useful life | hours | `null` if no prediction available — never `0` |
| `rul_lower` | Lower bound of RUL confidence interval | hours | `null` if unavailable |
| `rul_upper` | Upper bound of RUL confidence interval | hours | `null` if unavailable |
| `rul_confidence` | Model confidence in RUL estimate | 0–1 | `null` if unavailable |
| `failure_probability_24h` | Probability of failure within 24 hours | 0–1 | `null` if unavailable |
| `failure_probability_72h` | Probability of failure within 72 hours | 0–1 | `null` if unavailable |
| `failure_probability_mission` | Probability of failure within mission window | 0–1 | `null` if unavailable |
| `anomaly_score` | Degree of telemetry anomaly relative to baseline | 0–1 | `null` if no telemetry |
| `prediction_horizon_hours` | Duration over which prediction is valid | hours | — |
| `prediction_coverage_pct` | % of active assets with a valid current prediction | % | — |

**Display Rules:**
- Never display `null` as `0` in the UI — show "No data" or "—"
- Always display confidence bands when available
- Flag `low_confidence = true` when `rul_confidence < 0.5`

---

## 3. Maintenance KPIs

Displayed on `/maintenance` and `/dashboard`.

| KPI | Description | Source |
|---|---|---|
| `critical_work_orders` | Open work orders with priority = CRITICAL | `work_orders` |
| `high_priority_work_orders` | Open work orders with priority = HIGH | `work_orders` |
| `overdue_work_orders` | Work orders past target_completion and not closed | `work_orders` |
| `total_open_work_orders` | All open work orders | `work_orders` |
| `maintenance_backlog_hours` | Sum of estimated_duration_hours for all open work orders | `work_orders` |
| `completion_rate_7d` | % of work orders completed on time in last 7 days | `work_orders` |
| `blocking_mission_count` | Open work orders with `blocks_mission = true` | `work_orders` |

**Priority Scoring Formula:**

```
Priority Score = (W_risk × failure_probability) + (W_urgency × urgency_score) + (W_impact × mission_impact_score)

Weights (configurable defaults):
  W_risk    = 0.45
  W_urgency = 0.35
  W_impact  = 0.20

urgency_score         = 1 / max(hours_until_next_mission, 1)  (normalised 0–1)
mission_impact_score  = asset_criticality × mission_criticality (0–1 each)
```

---

## 4. Mission KPIs

Displayed on `/missions` and `/dashboard`.

| KPI | Description | Source |
|---|---|---|
| `required_assets` | Number of assets required by mission | `mission_requirements` |
| `ready_assets_for_mission` | Required assets that are READY | readiness engine per mission |
| `at_risk_assets_for_mission` | Required assets that are AT_RISK | readiness engine per mission |
| `not_ready_assets_for_mission` | Required assets that are NOT_READY | readiness engine per mission |
| `mission_readiness_gap` | `required_assets - ready_assets_for_mission` | calculated |
| `mission_readiness_pct` | `ready / required * 100` | calculated |
| `next_mission_hours_away` | Hours until next scheduled mission | `missions` |

**Mission Readiness Classification:**
- `MISSION_READY`: gap = 0 and no AT_RISK assets
- `MISSION_AT_RISK`: gap = 0 but ≥1 AT_RISK asset
- `MISSION_NOT_READY`: gap > 0

---

## 5. Data Quality KPIs

Displayed on `/data-quality` and used to qualify prediction confidence.

| KPI | Description | Source |
|---|---|---|
| `telemetry_freshness_pct` | % of sensors with data received in last N minutes | `telemetry`, `sensors` |
| `missing_telemetry_count` | Sensors with no data in expected window | `telemetry_quality` |
| `stale_sensor_count` | Sensors with no update beyond stale threshold | `telemetry_quality` |
| `stuck_sensor_count` | Sensors reporting constant value | `data_quality_events` |
| `sensor_drift_count` | Sensors with detected drift from baseline | `data_quality_events` |
| `outlier_event_count` | Telemetry readings flagged as outliers | `data_quality_events` |
| `data_quality_score` | Composite quality score (0–1) | calculated per asset |
| `prediction_confidence_impact` | % of predictions degraded due to data quality | `predictions` |
| `affected_assets_count` | Assets with ≥1 active data quality event | `data_quality_events` |

**Data Quality Score Calculation (per asset):**

```
dq_score = (
    w_freshness × freshness_score
    + w_completeness × completeness_score
    + w_range × range_score
    + w_consistency × consistency_score
)

Default weights: all equal (0.25 each)
```

---

## 6. Model Performance KPIs

Displayed on `/models` (ML Engineer and Admin roles only).

| KPI | Description |
|---|---|
| `rul_mae` | Mean Absolute Error on RUL holdout (hours) |
| `rul_rmse` | Root Mean Squared Error on RUL holdout (hours) |
| `rul_r2` | R² score on RUL holdout |
| `failure_risk_precision` | Precision of failure risk classifier on holdout |
| `failure_risk_recall` | Recall of failure risk classifier on holdout |
| `failure_risk_f1` | F1 score of failure risk classifier on holdout |
| `failure_risk_pr_auc` | Precision-Recall AUC of failure risk classifier |
| `anomaly_precision` | Precision of anomaly detector on labelled events |
| `anomaly_recall` | Recall of anomaly detector on labelled events |
| `false_positive_rate` | Alert false positive rate |
| `false_negative_rate` | Alert false negative rate (missed failures) |
| `calibration_error` | Expected Calibration Error (ECE) |
| `prediction_coverage_pct` | % of active assets with a valid current prediction |
| `inference_latency_p99_ms` | 99th percentile model inference latency |

---

## 7. KPI Threshold Table (Configurable)

| KPI | Green | Amber | Red |
|---|---|---|---|
| `readiness_pct` | ≥ 80% | 60–79% | < 60% |
| `failure_probability_mission` | < 0.15 | 0.15–0.45 | > 0.45 |
| `rul_estimate` vs mission_duration | > 2× | 1.25–2× | < 1.25× |
| `anomaly_score` | < 0.3 | 0.3–0.6 | > 0.6 |
| `data_quality_score` | > 0.85 | 0.6–0.85 | < 0.6 |
| `telemetry_freshness_pct` | ≥ 95% | 80–94% | < 80% |
| `overdue_work_orders` | 0 | 1–3 | > 3 |

All thresholds are configurable at system level by Admin users; these are defaults.
