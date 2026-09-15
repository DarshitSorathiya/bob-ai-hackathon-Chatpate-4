# API.md — MissionReady AI

## Base URL

```
/api/v1
```

All requests and responses use `Content-Type: application/json`.
All timestamps are ISO-8601 UTC (e.g., `2026-01-15T08:30:00Z`).
Numerical predictions that are unavailable return `null`, never `0`.

---

## Standard Response Envelope

### Success

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-01-15T08:30:00Z"
  },
  "error": null
}
```

### Error

```json
{
  "success": false,
  "data": null,
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-01-15T08:30:00Z"
  },
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": {}
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Request body or param validation failure |
| `UNAUTHORIZED` | 401 | Missing or invalid JWT |
| `FORBIDDEN` | 403 | Valid user but insufficient role |
| `NOT_FOUND` | 404 | Resource does not exist |
| `CONFLICT` | 409 | Duplicate resource (e.g., email already registered) |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `NO_PREDICTION` | 404 | Asset has no current prediction available |
| `DATA_QUALITY_LOW` | 200 | Response includes data but confidence is degraded |

---

## Authentication

All routes except `/auth/*` and `/health` require:

```
Authorization: Bearer <jwt_token>
```

---

## Existing Routes (Implemented)

### `GET /health`
Returns `{"message": "ok"}`.

### `POST /auth/register`
```json
{
  "fullName": "string",
  "email": "string",
  "password": "string (min 8)",
  "confirmPassword": "string"
}
```
Response: `AuthResponse` (201)

### `POST /auth/login`
```json
{
  "email": "string",
  "password": "string"
}
```
Response: `AuthResponse`

### `POST /auth/google`
```json
{
  "id_token": "string"
}
```
Response: `AuthResponse`

### `GET /auth/me`
Response: `UserResponse`

### `POST /auth/forgot-password`
```json
{ "email": "string" }
```
Response: `{"message": "..."}` (stub — no email sent)

---

## Routes to Implement

---

### Dashboard

#### `GET /dashboard/summary`
**Auth:** Any role
**Description:** Fleet-level KPIs for the main dashboard.

**Response `data`:**
```json
{
  "fleet": {
    "total_assets": 1000,
    "ready_count": 820,
    "at_risk_count": 130,
    "not_ready_count": 40,
    "unknown_count": 10,
    "readiness_pct": 82.0
  },
  "next_mission": {
    "mission_id": "uuid",
    "mission_code": "BRAVO-07",
    "scheduled_start": "2026-01-16T06:00:00Z",
    "hours_away": 21.5,
    "mission_readiness_pct": 91.7,
    "readiness_gap": 1,
    "status": "MISSION_AT_RISK"
  },
  "maintenance": {
    "critical_work_orders": 3,
    "high_priority_work_orders": 12,
    "overdue_work_orders": 2,
    "blocking_mission_count": 1
  },
  "data_quality": {
    "data_quality_score": 0.94,
    "affected_assets_count": 8
  }
}
```

---

### Assets

#### `GET /assets`
**Auth:** Any role
**Query params:**
- `status` — filter by readiness status (`READY`, `AT_RISK`, `NOT_READY`, `UNKNOWN`)
- `asset_type` — filter by type
- `page`, `page_size` — pagination (default: page=1, page_size=50)
- `sort_by` — `readiness_status`, `asset_code`, `risk_score` (default: `risk_score DESC`)

**Response `data`:**
```json
{
  "assets": [
    {
      "asset_id": "uuid",
      "asset_code": "AH-64-02",
      "asset_type": "HELICOPTER",
      "call_sign": "Bravo-2",
      "readiness_status": "AT_RISK",
      "readiness_reason": "Tail rotor bearing approaching overhaul interval",
      "failure_probability_mission": 0.38,
      "rul_estimate": 18.0,
      "anomaly_score": 0.52,
      "data_quality_score": 0.91,
      "last_telemetry_at": "2026-01-15T07:45:00Z"
    }
  ],
  "total": 1000,
  "page": 1,
  "page_size": 50
}
```

#### `GET /assets/{asset_id}`
**Auth:** Any role
**Response `data`:** Full asset detail (all fields above plus component list and maintenance summary).

#### `GET /assets/{asset_id}/telemetry`
**Auth:** reliability_engineer, admin
**Query params:**
- `sensor_id` — optional filter
- `from`, `to` — ISO-8601 time range (default: last 24 hours)
- `limit` — max rows per sensor (default: 500)

**Response `data`:**
```json
{
  "asset_id": "uuid",
  "sensors": [
    {
      "sensor_id": "uuid",
      "sensor_code": "VIB_ROTOR_TAIL",
      "sensor_type": "VIBRATION_RMS",
      "unit": "mm/s",
      "readings": [
        { "recorded_at": "2026-01-15T07:45:00Z", "value": 4.8, "quality_flag": null }
      ]
    }
  ]
}
```

#### `GET /assets/{asset_id}/components`
**Auth:** Any role
**Response `data`:** List of components with their latest health indicators.

#### `GET /assets/{asset_id}/predictions`
**Auth:** Any role
**Response `data`:** Latest prediction for each component, plus asset-level readiness.

---

### Missions

#### `GET /missions`
**Auth:** Any role
**Query params:** `status` filter, `from`/`to` date range, `page`/`page_size`

**Response `data`:**
```json
{
  "missions": [
    {
      "mission_id": "uuid",
      "mission_code": "BRAVO-07",
      "name": "Operation Bravo",
      "scheduled_start": "2026-01-16T06:00:00Z",
      "duration_hours": 24.0,
      "criticality": "HIGH",
      "status": "PLANNED",
      "readiness_summary": {
        "required_assets": 12,
        "ready_assets": 11,
        "at_risk_assets": 1,
        "not_ready_assets": 0,
        "mission_readiness_pct": 91.7,
        "mission_readiness_status": "MISSION_AT_RISK"
      }
    }
  ],
  "total": 45
}
```

#### `GET /missions/{mission_id}`
**Auth:** Any role
**Response `data`:** Full mission detail including per-asset readiness breakdown and substitution recommendations.

---

### Maintenance

#### `GET /maintenance/work-orders`
**Auth:** Any role
**Query params:** `status`, `priority`, `asset_id`, `blocks_mission`, `page`/`page_size`, `sort_by`

#### `GET /maintenance/work-orders/{id}`
**Auth:** Any role

#### `POST /maintenance/work-orders`
**Auth:** `maintainer`, `admin`
```json
{
  "asset_id": "uuid",
  "component_id": "uuid",
  "title": "string",
  "description": "string",
  "priority": "HIGH",
  "blocks_mission": false,
  "estimated_duration_hours": 3.5,
  "target_completion": "2026-01-16T04:00:00Z"
}
```

#### `PATCH /maintenance/work-orders/{id}`
**Auth:** `maintainer`, `admin`
```json
{
  "status": "COMPLETED",
  "actual_duration_hours": 3.2
}
```

---

### Alerts

#### `GET /alerts`
**Auth:** Any role
**Query params:** `status`, `severity`, `asset_id`, `page`/`page_size`

#### `POST /alerts/{id}/acknowledge`
**Auth:** Any role
Response: updated alert object.

---

### Data Quality

#### `GET /data-quality`
**Auth:** Any role
**Response `data`:**
```json
{
  "summary": {
    "overall_score": 0.94,
    "missing_telemetry_count": 5,
    "stale_sensor_count": 3,
    "affected_assets_count": 8
  },
  "events": [
    {
      "event_id": "uuid",
      "asset_code": "AH-64-02",
      "sensor_code": "HYDRAULIC_PRES",
      "event_type": "STALE",
      "severity": "HIGH",
      "started_at": "2026-01-15T06:00:00Z",
      "prediction_confidence_impact": "Prediction confidence reduced to 0.61"
    }
  ]
}
```

---

### Models

#### `GET /models`
**Auth:** `reliability_engineer`, `ml_engineer`, `admin`

#### `GET /models/{id}`
**Auth:** `reliability_engineer`, `ml_engineer`, `admin`
**Response `data`:** Model version details, metrics, feature list.

---

### Predictions / Explanations

#### `GET /predictions/{id}/explanation`
**Auth:** Any role
**Response `data`:**
```json
{
  "prediction_id": "uuid",
  "asset_code": "AH-64-02",
  "readiness_status": "AT_RISK",
  "rul_estimate": 18.0,
  "failure_probability_mission": 0.38,
  "contributing_factors": [
    {
      "factor": "VIBRATION_SPIKE",
      "description": "Tail rotor bearing vibration at 4.8 mm/s (+42% above baseline of 2.1 mm/s)",
      "weight": 0.55
    },
    {
      "factor": "OVERHAUL_PROXIMITY",
      "description": "Component at 485/500 operating hours (97% of overhaul interval)",
      "weight": 0.30
    },
    {
      "factor": "SERVICE_LOG_PATTERN",
      "description": "3 consecutive service logs noted vibration during maneuvers",
      "weight": 0.15
    }
  ]
}
```

---

### AI Copilot

#### `POST /copilot/query`
**Auth:** Any role
```json
{
  "conversation_id": "uuid|null",
  "message": "Why is AH-64-02 at risk?"
}
```

**Response `data`:**
```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "response": "AH-64-02 is classified AT_RISK due to a 42% increase in tail rotor bearing vibration...",
  "evidence": [
    {
      "evidence_type": "prediction",
      "reference_id": "uuid",
      "summary": "Failure probability: 38%, RUL: 18h"
    },
    {
      "evidence_type": "telemetry",
      "summary": "Vibration: 4.8 mm/s (baseline: 2.1 mm/s)"
    }
  ]
}
```

#### `GET /copilot/conversations/{id}`
**Auth:** Owner or admin
**Response `data`:** Conversation with all messages.

---

### Real-Time Events

#### `GET /events`
**Auth:** Any role
**Type:** Server-Sent Events (SSE)

Events are JSON objects with shape:
```json
{
  "event": "alert.created",
  "data": {
    "alert_id": "uuid",
    "severity": "CRITICAL",
    "asset_code": "AH-64-02"
  }
}
```

Event types: `telemetry.updated`, `prediction.updated`, `alert.created`, `alert.resolved`,
`work_order.updated`, `mission.readiness_changed`

---

## Pagination

All list endpoints use:
```json
{
  "total": 1000,
  "page": 1,
  "page_size": 50,
  "total_pages": 20
}
```

---

## Rate Limiting

| Endpoint | Limit |
|---|---|
| `POST /auth/login` | 10 requests / minute / IP |
| `POST /auth/register` | 5 requests / minute / IP |
| `POST /copilot/query` | 30 requests / minute / user |
| All other authenticated routes | 300 requests / minute / user |
