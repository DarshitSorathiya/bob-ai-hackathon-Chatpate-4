# DATA_MODEL.md — MissionReady AI

## Overview

All tables use PostgreSQL. All timestamps are UTC. All tables include `created_at` and (where mutable) `updated_at`. Soft deletion (`is_active` / `deleted_at`) is used for assets, sensors, users, and work orders to preserve history.

Primary keys are `BIGINT GENERATED ALWAYS AS IDENTITY` for high-volume tables and `UUID` for externally referenced entities. Asset IDs, mission IDs, and work order IDs use UUIDs to prevent enumeration.

---

## Domain: Fleet

### `assets`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
asset_code       VARCHAR(50) UNIQUE NOT NULL         -- e.g. "AH-64-02"
asset_type       VARCHAR(100) NOT NULL                -- e.g. "HELICOPTER"
call_sign        VARCHAR(100)
description      TEXT
manufacturer     VARCHAR(100)
model_number     VARCHAR(100)
serial_number    VARCHAR(100)
commission_date  DATE
total_hours      FLOAT NOT NULL DEFAULT 0
is_active        BOOLEAN NOT NULL DEFAULT TRUE
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

*Indexes:* `asset_code`, `is_active`

---

### `components`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
asset_id         UUID NOT NULL REFERENCES assets(id)
component_code   VARCHAR(100) NOT NULL
component_type   VARCHAR(100) NOT NULL     -- e.g. "ENGINE_CORE", "BEARING_1"
name             VARCHAR(200) NOT NULL
manufacturer     VARCHAR(100)
part_number      VARCHAR(100)
installation_date DATE
total_hours      FLOAT NOT NULL DEFAULT 0
mtbf_hours       FLOAT                   -- Mean Time Between Failures
is_active        BOOLEAN NOT NULL DEFAULT TRUE
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE (asset_id, component_code)
```

*Indexes:* `asset_id`, `component_type`

---

### `sensors`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
component_id     UUID NOT NULL REFERENCES components(id)
asset_id         UUID NOT NULL REFERENCES assets(id)
sensor_code      VARCHAR(100) NOT NULL
sensor_type      VARCHAR(100) NOT NULL    -- e.g. "VIBRATION_RMS", "TEMP_ENGINE"
unit             VARCHAR(50)              -- e.g. "mm/s", "°C", "PSI"
nominal_min      FLOAT
nominal_max      FLOAT
critical_min     FLOAT
critical_max     FLOAT
is_active        BOOLEAN NOT NULL DEFAULT TRUE
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE (asset_id, sensor_code)
```

*Indexes:* `asset_id`, `component_id`

---

## Domain: Telemetry

### `telemetry`

High-volume time-series table. Partitioned by `recorded_at` (monthly partitions recommended for production).

```sql
id               BIGINT GENERATED ALWAYS AS IDENTITY
asset_id         UUID NOT NULL REFERENCES assets(id)
sensor_id        UUID NOT NULL REFERENCES sensors(id)
component_id     UUID NOT NULL REFERENCES components(id)
value            FLOAT NOT NULL
recorded_at      TIMESTAMPTZ NOT NULL
ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now()
source           VARCHAR(50) DEFAULT 'simulator'   -- 'simulator', 'live', 'synthetic'
operating_hours  FLOAT                             -- asset operating hours at reading
operating_condition VARCHAR(50)                    -- e.g. "CRUISE", "TAKEOFF"

PRIMARY KEY (id, recorded_at)   -- composite for partitioning
```

*Indexes:* `(asset_id, sensor_id, recorded_at DESC)`, `(asset_id, recorded_at DESC)`

---

### `telemetry_quality`

One row per (sensor, time bucket). Tracks quality state per aggregation window.

```sql
id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
asset_id         UUID NOT NULL REFERENCES assets(id)
sensor_id        UUID NOT NULL REFERENCES sensors(id)
bucket_start     TIMESTAMPTZ NOT NULL
bucket_end       TIMESTAMPTZ NOT NULL
reading_count    INT NOT NULL DEFAULT 0
expected_count   INT NOT NULL
missing_count    INT NOT NULL DEFAULT 0
outlier_count    INT NOT NULL DEFAULT 0
freshness_seconds FLOAT                -- seconds since last reading at bucket_end
quality_score    FLOAT CHECK (quality_score >= 0 AND quality_score <= 1)
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE (sensor_id, bucket_start)
```

*Indexes:* `(asset_id, bucket_start DESC)`, `(sensor_id, bucket_start DESC)`

---

### `data_quality_events`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
asset_id         UUID NOT NULL REFERENCES assets(id)
sensor_id        UUID REFERENCES sensors(id)       -- null = asset-level event
event_type       VARCHAR(50) NOT NULL               -- see types below
severity         VARCHAR(20) NOT NULL               -- LOW, MEDIUM, HIGH, CRITICAL
description      TEXT
started_at       TIMESTAMPTZ NOT NULL
resolved_at      TIMESTAMPTZ
is_active        BOOLEAN NOT NULL DEFAULT TRUE
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

Event types: `MISSING`, `STALE`, `STUCK`, `DRIFT`, `OUTLIER`, `DUPLICATE`, `DELAYED`,
`OUT_OF_ORDER`, `NOISY`, `DROPOUT`, `IMPOSSIBLE_VALUE`

*Indexes:* `(asset_id, is_active)`, `(sensor_id, started_at DESC)`

---

## Domain: Maintenance

### `maintenance_events`

Historical record of completed maintenance.

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
asset_id         UUID NOT NULL REFERENCES assets(id)
component_id     UUID REFERENCES components(id)
event_type       VARCHAR(100) NOT NULL    -- INSPECTION, REPLACEMENT, OVERHAUL, REPAIR
description      TEXT
technician_notes TEXT
performed_at     TIMESTAMPTZ NOT NULL
asset_hours_at_event FLOAT
performed_by     UUID REFERENCES users(id)
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

*Indexes:* `(asset_id, performed_at DESC)`, `component_id`

---

### `work_orders`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
asset_id         UUID NOT NULL REFERENCES assets(id)
component_id     UUID REFERENCES components(id)
title            VARCHAR(300) NOT NULL
description      TEXT
priority         VARCHAR(20) NOT NULL        -- CRITICAL, HIGH, MEDIUM, LOW
status           VARCHAR(20) NOT NULL        -- OPEN, IN_PROGRESS, COMPLETED, DEFERRED, CANCELLED
priority_score   FLOAT                       -- calculated maintenance priority score
failure_probability FLOAT                    -- driving risk at time of creation
rul_at_creation  FLOAT                       -- RUL when work order was opened
blocks_mission   BOOLEAN NOT NULL DEFAULT FALSE
related_mission_id UUID REFERENCES missions(id)
estimated_duration_hours FLOAT
actual_duration_hours FLOAT
target_completion TIMESTAMPTZ
actual_completion TIMESTAMPTZ
created_by       UUID REFERENCES users(id)
assigned_to      UUID REFERENCES users(id)
evidence         JSONB                       -- contributing signals and explanations
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

*Indexes:* `(asset_id, status)`, `(priority, status)`, `target_completion`, `blocks_mission`

---

## Domain: Missions

### `missions`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
mission_code     VARCHAR(100) UNIQUE NOT NULL
name             VARCHAR(300) NOT NULL
description      TEXT
criticality      VARCHAR(20) NOT NULL DEFAULT 'MEDIUM'   -- LOW, MEDIUM, HIGH, CRITICAL
scheduled_start  TIMESTAMPTZ NOT NULL
duration_hours   FLOAT NOT NULL
scheduled_end    TIMESTAMPTZ GENERATED ALWAYS AS (scheduled_start + duration_hours * interval '1 hour') STORED
status           VARCHAR(20) NOT NULL DEFAULT 'PLANNED'  -- PLANNED, ACTIVE, COMPLETED, CANCELLED
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

*Indexes:* `scheduled_start`, `status`

---

### `mission_requirements`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
mission_id       UUID NOT NULL REFERENCES missions(id)
asset_type       VARCHAR(100) NOT NULL
quantity_required INT NOT NULL DEFAULT 1
min_rul_hours    FLOAT          -- minimum acceptable RUL for this mission
max_failure_probability FLOAT  -- maximum acceptable failure probability
notes            TEXT
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE (mission_id, asset_type)
```

---

### `mission_assignments`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
mission_id       UUID NOT NULL REFERENCES missions(id)
asset_id         UUID NOT NULL REFERENCES assets(id)
role             VARCHAR(100)          -- role of this asset in the mission
readiness_at_assignment VARCHAR(20)   -- readiness status when assigned
assigned_at      TIMESTAMPTZ NOT NULL DEFAULT now()
assigned_by      UUID REFERENCES users(id)

UNIQUE (mission_id, asset_id)
```

*Indexes:* `mission_id`, `asset_id`

---

## Domain: ML

### `features`

Pre-computed feature snapshot used as model input (stored for audit/reproducibility).

```sql
id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
asset_id         UUID NOT NULL REFERENCES assets(id)
component_id     UUID REFERENCES components(id)
computed_at      TIMESTAMPTZ NOT NULL
feature_window_hours FLOAT           -- rolling window used
features         JSONB NOT NULL      -- feature name → value mapping
source_version   VARCHAR(50)         -- feature pipeline version
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

*Indexes:* `(asset_id, computed_at DESC)`

---

### `predictions`

One row per prediction inference run (immutable once written).

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
asset_id         UUID NOT NULL REFERENCES assets(id)
component_id     UUID REFERENCES components(id)
model_version_id UUID NOT NULL REFERENCES model_versions(id)
feature_id       BIGINT REFERENCES features(id)
predicted_at     TIMESTAMPTZ NOT NULL DEFAULT now()

-- RUL outputs
rul_estimate     FLOAT      -- null = unavailable
rul_lower        FLOAT
rul_upper        FLOAT
rul_confidence   FLOAT      -- 0–1

-- Failure risk outputs
failure_probability_24h     FLOAT
failure_probability_72h     FLOAT
failure_probability_mission FLOAT
prediction_horizon_hours    FLOAT

-- Anomaly outputs
anomaly_score    FLOAT      -- 0–1

-- Readiness output
readiness_status VARCHAR(20)   -- READY, AT_RISK, NOT_READY, UNKNOWN
readiness_reason VARCHAR(200)
contributing_factors JSONB    -- list of {factor, value, weight} objects
data_quality_score FLOAT

-- Metadata
is_valid         BOOLEAN NOT NULL DEFAULT TRUE
invalidated_at   TIMESTAMPTZ
invalidation_reason VARCHAR(200)
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

*Indexes:* `(asset_id, predicted_at DESC)`, `(asset_id, readiness_status)`

*Rule:* Never update or delete prediction rows. Set `is_valid = false` if superseded.

---

### `failure_events`

Ground truth failure events (for model training and evaluation only).

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
asset_id         UUID NOT NULL REFERENCES assets(id)
component_id     UUID REFERENCES components(id)
failure_type     VARCHAR(100) NOT NULL
severity         VARCHAR(20) NOT NULL
occurred_at      TIMESTAMPTZ NOT NULL
detected_at      TIMESTAMPTZ
source           VARCHAR(50) NOT NULL    -- 'synthetic', 'historical', 'reported'
notes            TEXT
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

*Note:* `failure_events` is NEVER exposed as a feature to the ML model. Only used for labels.

---

### `model_versions`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
model_type       VARCHAR(50) NOT NULL    -- 'RUL', 'FAILURE_RISK', 'ANOMALY'
version_tag      VARCHAR(50) NOT NULL
algorithm        VARCHAR(100)
training_dataset VARCHAR(200)
trained_at       TIMESTAMPTZ NOT NULL
artifact_path    VARCHAR(500)
is_active        BOOLEAN NOT NULL DEFAULT FALSE
notes            TEXT
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()

UNIQUE (model_type, version_tag)
```

---

### `model_metrics`

```sql
id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
model_version_id UUID NOT NULL REFERENCES model_versions(id)
metric_name      VARCHAR(100) NOT NULL
metric_value     FLOAT NOT NULL
split            VARCHAR(50) NOT NULL    -- 'train', 'validation', 'test', 'holdout'
evaluated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
notes            TEXT

UNIQUE (model_version_id, metric_name, split)
```

---

## Domain: Operations

### `alerts`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
asset_id         UUID REFERENCES assets(id)
component_id     UUID REFERENCES components(id)
alert_type       VARCHAR(100) NOT NULL
severity         VARCHAR(20) NOT NULL    -- INFO, WARNING, CRITICAL
title            VARCHAR(300) NOT NULL
description      TEXT
status           VARCHAR(20) NOT NULL DEFAULT 'OPEN'  -- OPEN, ACKNOWLEDGED, RESOLVED
acknowledged_by  UUID REFERENCES users(id)
acknowledged_at  TIMESTAMPTZ
resolved_at      TIMESTAMPTZ
related_prediction_id UUID REFERENCES predictions(id)
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

*Indexes:* `(status, severity)`, `(asset_id, status)`

---

### `recommendations`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
asset_id         UUID REFERENCES assets(id)
component_id     UUID REFERENCES components(id)
recommendation_type VARCHAR(50) NOT NULL
title            VARCHAR(300) NOT NULL
description      TEXT
urgency          VARCHAR(20) NOT NULL    -- IMMEDIATE, HIGH, MEDIUM, LOW
rationale        TEXT
evidence         JSONB
related_prediction_id UUID REFERENCES predictions(id)
related_work_order_id UUID REFERENCES work_orders(id)
expires_at       TIMESTAMPTZ
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

---

## Domain: AI

### `copilot_conversations`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id          UUID NOT NULL REFERENCES users(id)
title            VARCHAR(300)
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

---

### `copilot_messages`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
conversation_id  UUID NOT NULL REFERENCES copilot_conversations(id)
role             VARCHAR(20) NOT NULL    -- 'user', 'assistant', 'tool'
content          TEXT NOT NULL
tool_call_name   VARCHAR(100)           -- if role = 'tool'
tool_call_args   JSONB                  -- logged for audit
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

*Indexes:* `(conversation_id, created_at ASC)`

---

### `copilot_evidence`

Evidence records attached to copilot responses.

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
message_id       UUID NOT NULL REFERENCES copilot_messages(id)
evidence_type    VARCHAR(50) NOT NULL   -- 'prediction', 'telemetry', 'maintenance', 'alert'
reference_id     UUID                   -- ID of the referenced object
reference_table  VARCHAR(100)
summary          TEXT
data_snapshot    JSONB                  -- copy of key fields at time of query
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

---

## Domain: Security

### `users` (existing)

```sql
id               BIGINT (auto-increment, existing)
full_name        VARCHAR(120)
email            VARCHAR(320) UNIQUE
password_hash    VARCHAR(255)
google_subject   VARCHAR(255) UNIQUE
auth_provider    VARCHAR(20)    -- 'password', 'google'
role             VARCHAR(30)    -- 'operator', 'maintainer', 'admin'
is_active        BOOLEAN
created_at       TIMESTAMPTZ
```

*Extension needed:* Add `updated_at` column.

---

### `audit_logs`

```sql
id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
user_id          UUID REFERENCES users(id)    -- null for system actions
request_id       UUID
action           VARCHAR(100) NOT NULL
resource_type    VARCHAR(100)
resource_id      VARCHAR(200)
before_state     JSONB
after_state      JSONB
ip_address       INET
user_agent       TEXT
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

*Indexes:* `(user_id, created_at DESC)`, `(resource_type, resource_id)`, `created_at DESC`

*Rule:* Audit logs are append-only. No updates or deletes.

---

## Migration Strategy

- Use **Alembic** for all schema changes.
- Never rely on `create_all()` for production schema beyond initial table creation.
- All migrations are forward-only.
- Before any new schema work in Phase 3, add `alembic` to `requirements.txt` and initialise `src/backend/migrations/`.
