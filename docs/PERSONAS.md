# PERSONAS.md — MissionReady AI

## Overview

Six primary personas use MissionReady AI. Every product decision must map to at least one persona's stated need. If a feature does not serve any persona below, it should not be built.

---

## Persona 1 — Operations Commander

**Who:** Senior officer responsible for fleet deployment decisions and mission authorisation.

**Environment:** Command centre or field operations room; high-pressure time constraints; mission windows measured in hours.

**Primary Questions:**
1. Is the fleet ready for tomorrow's mission?
2. Which assets are grounded, and why?
3. What is the readiness gap if I need to deploy 12 aircraft?
4. If Asset A is unavailable, which is the best substitute?
5. What changed since yesterday's briefing?

**What Serves Them Well:**
- Fleet readiness summary (KPI cards): total, ready, at-risk, not-ready, unknown
- Next mission readiness banner with gap count
- Plain-language summaries: "3 of 12 required assets are not ready. AH-64-02 has a tail rotor bearing replacement due before 06:00."
- Asset substitution recommendations
- Copilot natural-language answers with short, authoritative responses

**What Must Be Avoided:**
- Raw telemetry graphs (not their job)
- Model confidence scores or statistical jargon
- Overwhelming alert lists without triage
- Any AI response that invents operational data

**Dashboard Priority:** Highest — the opening view must answer their questions in under 10 seconds.

---

## Persona 2 — Maintenance Manager

**Who:** Senior maintenance technician or maintenance control officer managing a crew and work-order queue.

**Environment:** Maintenance bay, flightline office, or planning room; manages multiple personnel and a backlog of work orders.

**Primary Questions:**
1. What should the team work on first?
2. Which work orders are blocking tomorrow's mission?
3. What is the failure risk on Component X if we defer maintenance?
4. How much maintenance backlog exists?
5. Is there anything overdue?

**What Serves Them Well:**
- Prioritised work order queue with reasoning
- Estimated urgency and mission impact per work order
- RUL per component
- "Blocking mission" flag on work orders
- Ability to create and update work orders
- Overdue maintenance alerts

**What Must Be Avoided:**
- ML model explanations or feature importance (not their concern)
- Data quality dashboards unless it directly affects a work order
- Lengthy AI responses; they want actionable lists

---

## Persona 3 — Reliability Engineer

**Who:** Technical engineer responsible for understanding asset degradation, evaluating sensor data, and validating predictive model outputs.

**Environment:** Engineering workstation; has time to analyse; technical background in physics or engineering.

**Primary Questions:**
1. What is the degradation trend for Component Y over the past 30 days?
2. Is this vibration spike a real event or a sensor fault?
3. What is the predicted RUL with confidence bounds?
4. Which sensors are most correlated with failure?
5. Why did the anomaly score spike on 14 July?

**What Serves Them Well:**
- Telemetry time-series charts (multi-sensor)
- Anomaly score overlaid on telemetry
- RUL trend with confidence intervals
- Prediction explanation (feature contributions)
- Per-component degradation curve
- Data quality flags overlaid on telemetry

**What Must Be Avoided:**
- Oversimplified readiness status without drill-down
- Hiding data quality issues
- Opaque black-box predictions with no explanation

---

## Persona 4 — ML / Data Engineer

**Who:** Engineer responsible for building, evaluating, and monitoring the predictive models and data pipeline.

**Environment:** Development workstation; accesses model pages and data-quality dashboard; may run scripts directly.

**Primary Questions:**
1. What is the current model version and when was it last trained?
2. What are the MAE and RMSE on the holdout test set?
3. Is there evidence of concept drift?
4. What features does the model use?
5. Are there data quality issues affecting prediction coverage?

**What Serves Them Well:**
- Model version page: training date, dataset, metrics (MAE, RMSE, precision, recall, F1, PR-AUC)
- Feature list and importance
- Prediction coverage metric (% of assets with a valid current prediction)
- Data quality dashboard: missing sensors, stale data, coverage
- Model drift indicators

**What Must Be Avoided:**
- Hiding model version from the UI
- Replacing evaluation metrics with vague "accuracy %"
- Exposing model internals (weights, training data) to non-engineering roles

---

## Persona 5 — Executive / Observer

**Who:** Senior leader or observer (e.g., programme director, external auditor) who needs an at-a-glance view.

**Environment:** Tablet or presentation screen; limited technical background; periodic check-in.

**Primary Questions:**
1. What is the overall fleet readiness percentage?
2. Are any missions at risk?
3. What is the maintenance backlog trend?
4. Has the system helped prevent any failures this week?

**What Serves Them Well:**
- High-level KPI summary (readiness %, mission readiness, backlog count)
- Trend sparklines (readiness over time)
- Risk trend (at-risk count over 30 days)
- Clean, non-technical language throughout

**What Must Be Avoided:**
- Any technical details below KPI level
- Model metrics
- Raw telemetry

---

## Persona 6 — Admin

**Who:** System administrator responsible for platform configuration, user management, and audit compliance.

**Environment:** Administration interface; not a daily operational user.

**Primary Questions:**
1. Who has access to the system, and with what roles?
2. Who acknowledged this alert and when?
3. Who created this work order?
4. What configuration changes were made today?

**What Serves Them Well:**
- User management (create, edit, deactivate, assign roles)
- Audit log viewer (filterable by user, action, resource, date)
- System configuration (readiness thresholds, policy parameters)
- Model version management

**What Must Be Avoided:**
- Exposing sensitive operational data (e.g., classified mission names) in audit logs

---

## Persona → Feature Mapping

| Feature | Commander | Maint. Mgr | Reliability | ML Eng | Executive | Admin |
|---|---|---|---|---|---|---|
| Fleet readiness KPIs | ✅ Primary | ○ | ○ | ○ | ✅ Primary | — |
| Mission readiness banner | ✅ Primary | ✅ | ○ | — | ✅ | — |
| Work order queue | ○ | ✅ Primary | ○ | — | ○ | — |
| Asset detail + telemetry | ○ | ✅ | ✅ Primary | ○ | — | — |
| RUL + failure prediction | ○ | ✅ | ✅ Primary | ✅ | — | — |
| Prediction explanation | — | ✅ | ✅ Primary | ✅ | — | — |
| Anomaly detection | — | ○ | ✅ Primary | ✅ | — | — |
| Data quality dashboard | — | ○ | ✅ | ✅ Primary | — | — |
| Model performance page | — | — | ○ | ✅ Primary | — | — |
| Copilot chat | ✅ Primary | ✅ | ✅ | ○ | — | — |
| Asset substitution | ✅ Primary | — | — | — | — | — |
| User management | — | — | — | — | — | ✅ Primary |
| Audit log | — | — | — | — | — | ✅ Primary |
