# BOB_USAGE.md — MissionReady AI

## Purpose

This document records how IBM Bob was used throughout the MissionReady AI project and serves as evidence of Bob's role as the primary AI development partner. It also defines the conventions and standards for Bob usage going forward.

---

## Bob's Role in This Project

IBM Bob IDE was used as the primary AI development partner for every phase of this project. Bob was not used as a runtime end-user dependency; its role was exclusively in the software development process.

**Bob was used for:**

- Repository analysis (reading and understanding all existing code, configs, and documentation)
- Architecture planning (designing the full system before writing application code)
- Code generation (implementing features phase by phase)
- Code review (verifying correctness, security, and adherence to conventions)
- Security review (auditing routes, schemas, and credential handling)
- Documentation generation (producing RESEARCH.md, ARCHITECTURE.md, PERSONAS.md, KPIS.md, DATA_MODEL.md, API.md, SECURITY.md, IMPLEMENTATION_PLAN.md, BOB_USAGE.md)
- Testing (writing pytest suites and frontend test cases)
- Debugging (diagnosing test failures and integration issues)
- Repository-wide consistency checks (verifying no secrets, no leakage columns in features, role coverage on all routes)

---

## Phase 1 — Research & Architecture

### Bob Session: Initial Repository Inspection

**Tool used:** Bob Agent mode

**What was asked:**

> Analyse this codebase and produce docs/RESEARCH.md containing what exists, the runtime environment, installed packages, available datasets, existing code quality, environment variables, git branch summary, and unresolved questions.

**What Bob produced:**
- Read all source files in `src/backend/` and `src/frontend/`
- Identified Python 3.12.3 and Node 24.20.0 as the installed runtimes
- Identified that no ML packages (numpy, pandas, scikit-learn) are installed
- Identified that no dataset files exist
- Identified that all `docs/*.md` files are template placeholders
- Identified that PostgreSQL is not installed locally (no Docker either)
- Produced `docs/RESEARCH.md` with full findings

### Bob Session: Architecture Design

**Tool used:** Bob Plan mode → Bob Agent mode

**What was asked:**

> Design the full system architecture for MissionReady AI including: component map, data flow diagrams, ML architecture, readiness engine logic, authentication flow, real-time event architecture, technology stack. Produce docs/ARCHITECTURE.md.

**What Bob produced:**
- Full component map with ASCII diagram
- Telemetry → Readiness data flow
- Copilot query data flow
- Auth flow with JWT pattern
- SSE event architecture
- ML model specifications (RUL, Failure Risk, Anomaly)
- Target directory structure
- Technology stack rationale

### Bob Session: Planning Documents

**What was produced in this session:**
- `docs/PERSONAS.md` — Six personas with needs, feature mappings, and "what to avoid"
- `docs/KPIS.md` — All KPIs with source tables, calculations, thresholds, and formulas
- `docs/DATA_MODEL.md` — Full PostgreSQL schema with all tables, columns, indexes, constraints
- `docs/API.md` — All endpoint contracts, request/response shapes, error codes
- `docs/SECURITY.md` — Auth, RBAC, input validation, secret management, audit logging
- `docs/IMPLEMENTATION_PLAN.md` — 16-phase roadmap with gate criteria, risks, and dependency plan

---

## Bob Usage Conventions (All Future Phases)

### Mode Selection

| Task | Bob Mode |
|---|---|
| Architecture decisions, planning before coding | Plan mode |
| Implementation, code writing, file editing | Agent mode |
| Questions about codebase structure or decisions | Ask mode |
| Security review, code review | Agent mode with explicit review instruction |

### Bob Session Protocol (Per Feature)

Before starting any Bob session on a non-trivial feature:

**Step A — Plan:** Ask Bob to analyse requirements and existing code, identify files to change, list risks, describe tests required.

**Step B — Review:** Read the plan. If it violates architecture, correct it before proceeding.

**Step C — Implement:** Ask Bob to implement only the identified changes.

**Step D — Test:** Run `pytest` from `src/backend/` and `npm run lint` from `src/frontend/`.

**Step E — Review:** Ask Bob to perform a code review + security review of the changes.

**Step F — Fix:** Address any issues Bob identifies.

**Step G — Commit:** Create a meaningful commit.

**Step H — Export:** Export the Bob session transcript for `bob_sessions/`.

### Rules for Bob Instructions

1. Never ask Bob to make uncontrolled repository-wide changes.
2. Always give Bob the current `AGENTS.md` context so it knows the coding conventions.
3. Never ask Bob to commit credentials, API keys, or passwords.
4. When asking Bob to implement a route, explicitly state the required role check.
5. When asking Bob to add a model feature, explicitly state which columns are forbidden (true_rul, true_health, failure_events).
6. After each AI copilot session, ask Bob to review whether any hallucination guards were bypassed.

---

## Bob Sessions Evidence Log

Sessions are exported as screenshots and/or text transcripts and stored in `bob_sessions/`.

| Session ID | Phase | Description | Evidence File |
|---|---|---|---|
| BOB-001 | Phase 1 | Repository inspection and RESEARCH.md | `bob_sessions/BOB-001-research.md` |
| BOB-002 | Phase 1 | Architecture and planning documents | `bob_sessions/BOB-002-architecture.md` |
| *(future sessions will be added here)* | | | |

---

## How to Export a Bob Session

After each meaningful session:

1. In Bob, use the session history export if available.
2. Screenshot key interactions showing the plan, the code generated, and the review outcome.
3. Save to `bob_sessions/BOB-XXX-description.md` (or `.png` for screenshots).
4. Add an entry to the table above.

**Important:** Before exporting, scan the session for any accidentally visible credentials. Remove or redact them before saving to `bob_sessions/`.

---

## Bob Instructions File

The project maintains an `AGENTS.md` file at the repo root that is automatically loaded by Bob. It contains:

- Build/run/test commands
- Environment variable setup (especially the `.env` location)
- Backend coding conventions (type aliases, service pattern, role guards)
- Frontend coding conventions (API client, session storage, component conventions)

When Bob's context is reset, it will re-read `AGENTS.md` automatically. If major architecture decisions change, update `AGENTS.md` and the `.bob/rules-*/AGENTS.md` mode-specific files.
