# Bob Session BOB-002 — Architecture & Planning Documents

**Phase:** 1 (Research & Architecture)
**Mode:** Bob Agent
**Date:** 2025-07-15

## Task

Design the complete system architecture and produce all Phase 1 planning documents:
- docs/ARCHITECTURE.md
- docs/PERSONAS.md
- docs/KPIS.md
- docs/DATA_MODEL.md
- docs/API.md
- docs/SECURITY.md
- docs/IMPLEMENTATION_PLAN.md
- docs/BOB_USAGE.md

## Design Decisions Made

### Architecture
- Kept existing FastAPI backend and Next.js 14 App Router frontend.
- Added Alembic as migration tool (required before any new schema work).
- Chose SSE (Server-Sent Events) over WebSocket for real-time push — simpler for one-directional updates.
- Three separate ML models (RUL regression, Failure Risk classifier, Anomaly detector) — not one monolithic model.
- Readiness Engine is deterministic and rule-based; ML models only provide inputs to it.
- IBM watsonx.ai confined to the copilot layer only; does not replace ML models.
- All credentials (WATSONX_API_KEY) remain server-side; never proxied to browser.

### Data Model
- 20 tables spanning 8 domains: Fleet, Telemetry, Maintenance, Missions, ML, Operations, AI, Security.
- `predictions` table is immutable (no updates/deletes; use `is_valid=false` to supersede).
- `failure_events` and ground-truth fields are never stored in the `features` or `telemetry` tables.
- `audit_logs` is append-only.
- All timestamps in UTC. UUID primary keys for externally-referenced entities.

### Security
- argon2id password hashing (existing).
- JWT Bearer tokens; 60-minute expiry.
- Server-side RBAC via `require_roles()` on every protected route.
- All inputs validated by Pydantic v2 schemas.
- Audit log on all state-changing operations.

### API
- Standard envelope: `{success, data, meta, error}` on every response.
- Numerical predictions that are unavailable return `null`, never `0`.
- Rate limiting on auth endpoints (10 req/min/IP for login).

## Output Files Produced

| File | Lines |
|---|---|
| docs/ARCHITECTURE.md | 258 |
| docs/PERSONAS.md | 165 |
| docs/KPIS.md | 164 |
| docs/DATA_MODEL.md | 305 |
| docs/API.md | 298 |
| docs/SECURITY.md | 185 |
| docs/IMPLEMENTATION_PLAN.md | 325 |
| docs/BOB_USAGE.md | 137 |

## Unresolved Questions (Documented in IMPLEMENTATION_PLAN.md)

1. Local PostgreSQL availability — Docker vs. cloud DB.
2. Which watsonx.ai model is approved for the hackathon.
3. Whether WATSONX_API_KEY is already available.
4. Whether to migrate frontend to TypeScript (decision: new modules use .tsx; existing .jsx not renamed).
