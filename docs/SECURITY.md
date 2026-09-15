# SECURITY.md — MissionReady AI

## Security Principles

1. Defence in depth — multiple independent layers, not a single perimeter.
2. Least privilege — every user, service, and token has only the permissions required.
3. Fail secure — unexpected errors reject the request, not permit it.
4. No secrets in code — all credentials live in environment variables.
5. Auditability — every state-changing action is logged with user, timestamp, and context.
6. Separation of concerns — AI layer never receives credentials; ML layer never receives user data.

---

## Authentication

### Password Authentication

- Passwords hashed with **argon2id** via `pwdlib[argon2]`.
- Minimum 8 characters enforced at both frontend and backend.
- Password never logged, stored in plaintext, or returned in any response.
- Login endpoint returns a generic error ("Invalid email or password") regardless of which field is wrong — no enumeration.

### Google OAuth

- Backend verifies the Google ID token using `google.oauth2.id_token.verify_oauth2_token`.
- Client-provided email and role are **never trusted**; claims are extracted from the verified token only.
- `GOOGLE_CLIENT_ID` must be set server-side; Google sign-in is disabled when it is not set.

### JWT

- Algorithm: HS256.
- Secret: `JWT_SECRET_KEY` — must be at least 32 random bytes; generated with `python -c "import secrets; print(secrets.token_hex(32))"`.
- Expiry: configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 60 minutes).
- Subject (`sub`): `str(user.id)` — integer user ID as string.
- Tokens are validated on every protected request; expired or tampered tokens return 401.
- No refresh token in Phase 2 (acceptable for hackathon). Phase 13 security hardening will evaluate refresh token rotation.

### Token Storage

- Frontend stores the JWT in `localStorage` under key `missionready_access_token`.
- **Known risk**: localStorage is accessible to JavaScript; acceptable for hackathon scope. Production deployment should migrate to HttpOnly cookies.
- IBM watsonx.ai API key is **never sent to the browser** — only used server-side in `CopilotService`.

---

## Authorization (RBAC)

### Roles

| Role | String constant | Default for |
|---|---|---|
| Operator | `"operator"` | All new accounts |
| Maintainer | `"maintainer"` | Maintenance team |
| Admin | `"admin"` | System administrators |

Role constants live in `src/backend/app/core/roles.py`. Never use hardcoded strings in route guards.

### Permission Matrix

| Action | operator | maintainer | admin |
|---|---|---|---|
| Read fleet/assets | ✅ | ✅ | ✅ |
| Read missions | ✅ | ✅ | ✅ |
| Read alerts | ✅ | ✅ | ✅ |
| Read predictions | ✅ | ✅ | ✅ |
| Use copilot | ✅ | ✅ | ✅ |
| Read telemetry (raw) | ❌ | ✅ | ✅ |
| Read explanations | ✅ | ✅ | ✅ |
| Acknowledge alerts | ✅ | ✅ | ✅ |
| Create work orders | ❌ | ✅ | ✅ |
| Update work orders | ❌ | ✅ | ✅ |
| Read model metrics | ❌ | ❌ | ✅ |
| Manage users | ❌ | ❌ | ✅ |
| View audit logs | ❌ | ❌ | ✅ |
| System configuration | ❌ | ❌ | ✅ |

*Future roles (`reliability_engineer`, `ml_engineer`) defined in spec will be added in Phase 3.*

### Enforcement

- Route guards use `Depends(require_roles(...))` from `src/backend/app/api/deps.py`.
- Authorization is **always server-side**. Frontend may hide UI elements for UX, but the API always re-enforces roles.
- The `CurrentUser` dependency validates the JWT and retrieves the live user record (active check included) on every request.

---

## Input Validation

- All request bodies validated by **Pydantic v2** schemas.
- Email validation: `email-validator` library (enforces RFC compliance).
- String length limits on all text fields (see schema definitions).
- Enum fields validated against allowed values.
- FastAPI returns 422 with field-level error details on validation failure.
- No user-supplied data is ever interpolated into raw SQL strings — SQLAlchemy ORM exclusively.

---

## Output Validation

- Response models defined as Pydantic `response_model` on every endpoint.
- Sensitive fields (e.g., `password_hash`, `google_subject`) are explicitly excluded from all response schemas.
- `model_config = ConfigDict(from_attributes=True)` used on ORM-backed response models.

---

## Rate Limiting

| Endpoint | Limit | Rationale |
|---|---|---|
| `POST /auth/login` | 10 req/min/IP | Brute-force protection |
| `POST /auth/register` | 5 req/min/IP | Account creation throttle |
| `POST /copilot/query` | 30 req/min/user | watsonx.ai cost protection |
| All other authenticated | 300 req/min/user | General abuse protection |

Implementation: `slowapi` library (wraps `limits` / `redis` backend optional).

---

## Security Headers

Apply via FastAPI middleware:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

CORS: configured via `CORSMiddleware`; `allow_origins` comes from `settings.cors_origin_list` (comma-separated env var). Never set to `["*"]` with `allow_credentials=True`.

---

## SQL Injection Prevention

- All database queries use **SQLAlchemy ORM** (`select(User).where(...)` style) or parameterised `text()` expressions.
- Raw string interpolation in SQL is forbidden.
- Code review checklist item: search for any `f"SELECT..."` or `.execute(f"...")`; they must not exist.

---

## XSS Prevention

- Backend returns JSON only; no HTML rendering.
- Frontend uses React (escapes by default); no `dangerouslySetInnerHTML` in any component.
- Copilot responses are rendered as text, never as raw HTML.

---

## CSRF Protection

- The API uses JWT Bearer tokens (header-based), not session cookies.
- Cookie-based sessions are not used in the current architecture, so traditional CSRF is not applicable.
- If HttpOnly cookie tokens are introduced in Phase 13, add CSRF double-submit cookie pattern.

---

## Secret Management

Rules (enforced by code review):

1. No API keys, passwords, or tokens in source code.
2. All secrets in `src/.env` (gitignored).
3. `src/.env.example` contains placeholder values only.
4. No `print()` or `logger.debug()` calls that log secret values.
5. `WATSONX_API_KEY` and `WATSONX_PROJECT_ID` must never appear in any frontend code, browser request, or copilot response.
6. JWT signing secret must be at least 32 random bytes.
7. Database password must be unique (not reused from other services).

---

## Audit Logging

Every state-changing action writes a row to `audit_logs`:

| Event | Logged fields |
|---|---|
| Login (success/failure) | user_id, IP, user_agent, timestamp |
| Logout | user_id, timestamp |
| Register | user_id, email, timestamp |
| Work order created | user_id, work_order_id, asset_id, priority |
| Work order updated | user_id, work_order_id, before/after status |
| Alert acknowledged | user_id, alert_id, timestamp |
| Mission assignment changed | user_id, mission_id, asset_id |
| Copilot tool call | user_id, tool_name, args (sanitised), conversation_id |
| Model version activated | user_id, model_version_id, model_type |
| System config changed | user_id, config_key, before/after value |

Audit log rows are **append-only**. No update or delete operations are permitted on `audit_logs`.

---

## Dependency Security

Phase 13 hardening steps:

- Run `pip audit` (or `safety check`) on `requirements.txt`.
- Run `npm audit` on frontend dependencies.
- Pin all production dependency versions (no `^` or `~` in `requirements.txt`).
- Add `bandit` static analysis to CI pipeline.

---

## AI Safety Rules

These rules are enforced in `CopilotService`:

1. The AI copilot **never** invents telemetry values, RUL estimates, or maintenance records.
2. Every claim in a copilot response must be grounded in a backend tool call result.
3. Tool call arguments are validated before execution.
4. Tool call results are logged to `copilot_evidence`.
5. The copilot cannot create, update, or delete records — it is read-only.
6. Copilot tool access is restricted by the requesting user's role.
7. The copilot explicitly states when data quality is poor or confidence is low.
8. The copilot explicitly distinguishes predictions ("the model estimates...") from facts ("the service log records...").
9. IBM watsonx.ai API key is passed only within the `CopilotService` server-side call — never proxied or returned to the frontend.

---

## Known Limitations (Acceptable for Hackathon)

1. **JWT in localStorage** — preferred production approach is HttpOnly cookie. Mitigation: short token expiry (60 min).
2. **No refresh token** — users must re-authenticate after expiry.
3. **`forgot-password` stub** — returns static message; no email is sent. Documented as known limitation.
4. **No TLS enforcement in dev** — Docker Compose local setup uses plain HTTP. Production deployment requires HTTPS.
5. **No Redis for rate limiting** — in-memory rate limiting loses state on restart. Acceptable for demo.
