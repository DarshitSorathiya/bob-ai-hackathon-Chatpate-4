# 🎬 MissionReady Copilot — Demo Video Script

**Team:** Chatpate-4  
**Track:** AI  
**Target Length:** 4–5 minutes  
**Narration style:** Confident, clear, no filler words. Speak as a product demo, not a tutorial.

---

## 🎙️ Pre-recording checklist

- [ ] Browser at 1280×720, zoom at 100%, dark-mode browser if possible
- [ ] App running locally: `docker compose up -d` (or live URL)
- [ ] Demo data seeded: `docker compose exec backend python scripts/seed_demo_data.py`
- [ ] Microphone levels tested
- [ ] Screen recorder capturing browser + audio (OBS / Loom / QuickTime)
- [ ] Start on the **Landing Page** (`http://localhost:3000`)

---

## ⏱️ Scene-by-Scene Script

---

### SCENE 1 — Hook & Problem Statement `[0:00 – 0:30]`

**Screen:** Landing page (`/`)

> **Narrator:**
> "Military fleets rely on hundreds of assets — helicopters, armored vehicles, transport aircraft. Before every mission, commanders need one critical answer: *which assets are ready to deploy, and which ones are about to fail?*
>
> Today, that answer comes from fixed maintenance schedules, manual logbooks, and gut instinct — too slow, too opaque, and too often wrong.
>
> This is **MissionReady Copilot** — an AI-powered predictive maintenance and mission readiness platform built by Team Chatpate-4 for the IBM Bob Hackathon."

**Action:** Let the landing page sit for 2 seconds, then click **Get Started** or **Login**.

---

### SCENE 2 — Authentication `[0:30 – 0:50]`

**Screen:** Login page (`/login`) → Dashboard

> **Narrator:**
> "We log in as a Maintenance Commander — a role that has full access to fleet readiness, work orders, and the AI copilot."

**Action:**
1. Type credentials into the login form
2. Click **Sign In**
3. Wait for redirect to `/dashboard`

> **Narrator:**
> "The system authenticates via JWT and immediately loads the live fleet state."

---

### SCENE 3 — Fleet Dashboard `[0:50 – 1:45]`

**Screen:** Dashboard (`/dashboard`)

> **Narrator:**
> "The dashboard is the command view. In under 10 seconds, a commander knows exactly where the fleet stands."

**Action:** Slowly pan / scroll the dashboard. Point out each section as you mention it.

> **Narrator:**
> "At the top — four KPI cards.
> - **Total Assets:** how many platforms are in the fleet
> - **Ready:** cleared for immediate deployment
> - **At Risk:** predicted to fail within the mission window
> - **Not Ready:** grounded — cannot be deployed
>
> Below that, the **Mission Readiness Banner** — for tomorrow's scheduled mission, we need 8 aircraft. Right now, 2 are not ready. That's a readiness gap of 2. The system flags this immediately.
>
> The fleet readiness percentage — currently sitting at 67% — is in the amber zone. The system colour-codes thresholds: green above 80%, amber 60–79%, red below 60%.
>
> This entire view is updated in real time from the predictive ML pipeline."

---

### SCENE 4 — Asset List & Individual Asset Detail `[1:45 – 2:30]`

**Screen:** Assets list (`/assets`) → Asset detail (`/assets/[assetId]`)

> **Narrator:**
> "Clicking into the Assets page gives us the full fleet inventory with live readiness status per asset."

**Action:** Click on an **AT_RISK** asset (e.g., `AH-64-02`).

> **Narrator:**
> "Let's look at AH-64-02 — flagged AT RISK. Here's why the system made that call.
>
> The asset detail page shows:
> - **Remaining Useful Life** — predicted at 18 hours with a confidence band of 14–24 hours
> - **Failure probability within 24 hours** — 38%
> - **Anomaly score** — 0.71, well into the red zone
>
> Scrolling down, we see the HUMS telemetry charts. The tail rotor vibration sensor shows a +35% spike above baseline starting 48 hours ago — this is the primary driver of the AT_RISK classification.
>
> The explainability panel on the right tells the maintenance crew *exactly* what is causing the risk — not just a black-box score."

---

### SCENE 5 — Alerts `[2:30 – 2:50]`

**Screen:** Alerts page (`/alerts`)

> **Narrator:**
> "The Alerts page surfaces the most critical events across the fleet — anomaly detections, overdue maintenance, and prediction threshold breaches — triaged by priority so the crew focuses on what matters most, not just what happened most recently."

**Action:** Briefly scroll the alerts list. Point to a CRITICAL alert.

---

### SCENE 6 — Maintenance Work Orders `[2:50 – 3:20]`

**Screen:** Maintenance page (`/maintenance`)

> **Narrator:**
> "The Maintenance page is where the prioritised work order queue lives.
>
> These aren't just sorted by date — they're ranked by a priority score that combines failure probability, urgency relative to the next mission window, and asset criticality.
>
> Work orders with the **Blocks Mission** flag are surfaced at the top. The maintenance team knows exactly which jobs have to be done before 06:00 tomorrow."

**Action:** Point to a CRITICAL work order marked **Blocks Mission**.

---

### SCENE 7 — Missions `[3:20 – 3:40]`

**Screen:** Missions page (`/missions`)

> **Narrator:**
> "The Missions view gives a per-mission readiness breakdown. For each scheduled operation, the system shows how many required assets are ready, at risk, or not ready — and calculates a readiness gap.
>
> MISSION_NOT_READY means the gap is non-zero. MISSION_AT_RISK means all assets are ready but at least one is flagged as degraded. Commanders can make go / no-go decisions backed by data, not guesswork."

---

### SCENE 8 — AI Bob Copilot `[3:40 – 4:20]`

**Screen:** Copilot page (`/copilot`)

> **Narrator:**
> "This is where IBM Bob comes in. The AI Copilot is powered by IBM watsonx.ai — and this is the centrepiece of our IBM technology integration.
>
> Watch this."

**Action:** Type the following query into the copilot chat:

```
Which assets are blocking tomorrow's mission and what should the team do first?
```

Wait for the response. Let it render fully on screen.

> **Narrator:**
> "The copilot queries the live fleet data, the readiness engine output, and the work order queue — then produces a plain-language briefing with specific, actionable recommendations.
>
> No hallucinations — every answer is grounded in the real database state. The copilot is prohibited from inventing operational data.
>
> Let's ask one more."

**Action:** Type:

```
What is the predicted RUL for AH-64-02 and is it safe to deploy on the 18-hour mission tomorrow?
```

> **Narrator:**
> "The copilot cross-references the RUL prediction — 18 hours — against the mission duration — also 18 hours — and correctly advises: this asset is borderline. The RUL-to-mission ratio is 1.0, which falls into the red zone. The recommendation is to complete the tail rotor bearing service before deployment.
>
> That's IBM watsonx.ai turning raw ML predictions into an operational decision in seconds."

---

### SCENE 9 — Data Quality & Models `[4:20 – 4:40]`

**Screen:** Data Quality (`/data-quality`) → briefly → Models (`/models`)

> **Narrator:**
> "For our ML and reliability engineers — the Data Quality dashboard monitors every sensor in the fleet. Stale sensors, missing telemetry, and drift events are flagged here, and they directly influence prediction confidence scores.
>
> The Models page shows the live performance of our predictive models — RUL Mean Absolute Error, failure risk F1 score, and prediction coverage — so engineers know when the models need retraining."

**Action:** Quick scroll of each page — 5 seconds each.

---

### SCENE 10 — Close & Stack Summary `[4:40 – 5:00]`

**Screen:** Return to Dashboard

> **Narrator:**
> "MissionReady Copilot combines a FastAPI backend, a PostgreSQL database, a Next.js 14 frontend, and IBM watsonx.ai — all packaged in Docker and deployed in minutes.
>
> The full stack was designed and built with **IBM Bob** as our AI development partner — from architecture planning through code generation, testing, and documentation.
>
> Predictive maintenance. Mission-critical readiness. Powered by IBM.
>
> Team Chatpate-4."

**Action:** Let the dashboard sit for 2 seconds. End recording.

---

## 📋 Shot order summary

| # | Page | URL | Duration |
|---|---|---|---|
| 1 | Landing | `/` | 0:30 |
| 2 | Login | `/login` | 0:20 |
| 3 | Dashboard | `/dashboard` | 0:55 |
| 4 | Asset detail | `/assets/[id]` | 0:45 |
| 5 | Alerts | `/alerts` | 0:20 |
| 6 | Maintenance | `/maintenance` | 0:30 |
| 7 | Missions | `/missions` | 0:20 |
| 8 | Copilot | `/copilot` | 0:40 |
| 9 | Data Quality + Models | `/data-quality` `/models` | 0:20 |
| 10 | Dashboard (close) | `/dashboard` | 0:20 |
| **Total** | | | **~4:40** |

---

## 📸 Screenshots to capture (for `demo/screenshots/`)

Capture these during recording or separately:

| Filename | Page | What to show |
|---|---|---|
| `01-landing-page.png` | `/` | Full landing page above the fold |
| `02-dashboard-kpis.png` | `/dashboard` | KPI cards + mission readiness banner |
| `03-asset-detail-risk.png` | `/assets/[id]` | AT_RISK asset with RUL + telemetry chart |
| `04-copilot-response.png` | `/copilot` | IBM Bob copilot answering a mission query |
| `05-maintenance-queue.png` | `/maintenance` | Work order queue with Blocks Mission flag |
| `06-alerts-list.png` | `/alerts` | Critical alerts triaged list |

Minimum required by hackathon: 3. Recommended: all 6.

---

## 🎤 Narrator tips

- Speak at **~130 words/minute** — slightly slower than natural speech
- Pause 1 second after navigating to a new page before speaking
- Never apologise or say "um", "so basically", or "as you can see"
- Emphasise: **IBM Bob**, **IBM watsonx.ai**, **predictive**, **real-time**, **explainable**
- Keep copilot queries short — long queries scroll off screen
