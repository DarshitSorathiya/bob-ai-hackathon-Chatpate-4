"""
Data models for the Readiness Engine.

All models are pure dataclasses / enums — no database I/O occurs here.
The engine consumes ReadinessInput and produces ReadinessOutput.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class ReadinessStatus(str, enum.Enum):
    """Operational readiness classification.

    READY     — asset is fit for the requested mission window.
    AT_RISK   — asset can operate but has elevated risk; recommend monitoring.
    NOT_READY — asset must NOT be assigned; a blocking condition exists.
    UNKNOWN   — evidence is insufficient, stale, or unreliable; do NOT treat
                as READY.  Callers must explicitly handle this state.
    """

    READY = "READY"
    AT_RISK = "AT_RISK"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

class ReasonCode(str, enum.Enum):
    """Exhaustive catalogue of readiness reason codes.

    Each rule in ReadinessEngine maps to exactly one primary ReasonCode.
    Additional contributing factors may accompany the primary reason.
    """

    # NOT_READY reasons
    CRITICAL_MAINTENANCE_OPEN = "CRITICAL_MAINTENANCE_OPEN"
    """An open work order with blocking=True prevents mission assignment."""

    ASSET_UNDER_MAINTENANCE = "ASSET_UNDER_MAINTENANCE"
    """Asset is currently taken offline for scheduled or unscheduled maintenance."""

    CRITICAL_COMPONENT_FAILURE = "CRITICAL_COMPONENT_FAILURE"
    """One or more critical components are in a FAILED state."""

    RUL_BELOW_MISSION_REQUIREMENT = "RUL_BELOW_MISSION_REQUIREMENT"
    """RUL estimate (with safety margin) is less than the mission duration."""

    HIGH_FAILURE_PROBABILITY = "HIGH_FAILURE_PROBABILITY"
    """Failure probability exceeds the NOT_READY threshold."""

    SENSOR_FAULT_DETECTED = "SENSOR_FAULT_DETECTED"
    """A critical sensor has reported a fault condition; reading is invalid."""

    OVERDUE_CRITICAL_MAINTENANCE = "OVERDUE_CRITICAL_MAINTENANCE"
    """A mandatory maintenance task is past its due date by the critical window."""

    # UNKNOWN reasons — insufficient/unreliable evidence
    STALE_CRITICAL_TELEMETRY = "STALE_CRITICAL_TELEMETRY"
    """Last telemetry reading for one or more critical sensors exceeds the stale threshold."""

    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    """Not enough observations have been collected to produce a reliable prediction."""

    LOW_PREDICTION_CONFIDENCE = "LOW_PREDICTION_CONFIDENCE"
    """ML model confidence is below the minimum acceptable threshold."""

    NO_PREDICTION_AVAILABLE = "NO_PREDICTION_AVAILABLE"
    """No ML prediction record exists for this asset (right-censored or never run)."""

    PREDICTION_DATA_QUALITY_DEGRADED = "PREDICTION_DATA_QUALITY_DEGRADED"
    """High failure probability combined with poor data quality; confidence too low to act."""

    # AT_RISK reasons
    ELEVATED_FAILURE_PROBABILITY = "ELEVATED_FAILURE_PROBABILITY"
    """Failure probability is above the AT_RISK threshold but below NOT_READY threshold."""

    RUL_WITHIN_SAFETY_MARGIN = "RUL_WITHIN_SAFETY_MARGIN"
    """RUL is above the hard cutoff but below the recommended safety margin."""

    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    """Anomaly score is elevated; root cause not yet determined."""

    SENSOR_DRIFT = "SENSOR_DRIFT"
    """One or more sensors show gradual drift outside the nominal operating range."""

    OVERDUE_ROUTINE_MAINTENANCE = "OVERDUE_ROUTINE_MAINTENANCE"
    """A routine (non-critical) maintenance task is overdue."""

    # READY reason
    ALL_CHECKS_PASSED = "ALL_CHECKS_PASSED"
    """All readiness checks passed with acceptable margins."""


# ---------------------------------------------------------------------------
# Component and maintenance state enums
# ---------------------------------------------------------------------------

class ComponentState(str, enum.Enum):
    """Reported health state of a single component."""

    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    FAULT = "FAULT"      # sensor/component fault — distinguish from failure
    FAILED = "FAILED"    # outright failure requiring immediate attention
    UNKNOWN = "UNKNOWN"


class MaintenanceStatus(str, enum.Enum):
    """Current maintenance lifecycle state of the asset."""

    OPERATIONAL = "OPERATIONAL"
    """Asset is in service, no maintenance in progress."""

    SCHEDULED_MAINTENANCE = "SCHEDULED_MAINTENANCE"
    """Asset is pre-positioned or offline for upcoming scheduled maintenance."""

    UNDER_MAINTENANCE = "UNDER_MAINTENANCE"
    """Maintenance is actively in progress; asset is unavailable."""

    RETURNED_TO_SERVICE = "RETURNED_TO_SERVICE"
    """Maintenance has just been completed; asset is back in service."""


# ---------------------------------------------------------------------------
# Contributing factor
# ---------------------------------------------------------------------------

@dataclass
class ContributingFactor:
    """One piece of structured evidence attached to a readiness decision.

    Attributes:
        code:       The reason code for this factor.
        message:    Human-readable description.
        severity:   "critical" | "warning" | "info"
        evidence:   Raw supporting values (e.g. {"rul_hours": 12, "threshold": 50}).
    """

    code: ReasonCode
    message: str
    severity: str  # "critical" | "warning" | "info"
    evidence: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Thresholds (configurable, but with safe defaults)
# ---------------------------------------------------------------------------

@dataclass
class ReadinessThresholds:
    """Configurable policy thresholds.

    All numeric values use consistent units:
    - Probabilities: 0.0 – 1.0
    - Durations: hours
    - Ages: hours
    - Scores: 0.0 – 1.0 (anomaly score)

    Rule reference numbers correspond to the ordered checks in ReadinessEngine.
    """

    # --- Failure probability thresholds ---
    # Rule 5: failure_probability > not_ready_failure_prob → NOT_READY
    not_ready_failure_prob: float = 0.45
    # Rule 8: failure_probability > at_risk_failure_prob → AT_RISK
    at_risk_failure_prob: float = 0.15

    # --- RUL thresholds ---
    # Rule 6: rul_hours < mission_hours * not_ready_rul_margin → NOT_READY
    not_ready_rul_margin: float = 1.25
    # Rule 9: rul_hours < mission_hours * at_risk_rul_margin → AT_RISK
    at_risk_rul_margin: float = 2.0

    # --- Telemetry freshness ---
    # Rule 7: hours since last reading > stale_hours → UNKNOWN
    stale_hours: float = 4.0

    # --- Prediction confidence ---
    # Rule 7: model confidence < min_confidence → UNKNOWN
    min_confidence: float = 0.50

    # --- Anomaly score ---
    # Rule 10: anomaly_score > at_risk_anomaly_score → AT_RISK (advisory)
    at_risk_anomaly_score: float = 0.70

    # --- Overdue maintenance ---
    # Rule 4b: hours_overdue > critical_overdue_hours → NOT_READY
    critical_overdue_hours: float = 48.0
    # Rule 11: any overdue routine maintenance → AT_RISK
    routine_overdue_hours: float = 0.0   # any overdue = AT_RISK

    # --- Minimum observation count ---
    # Rule 7d: observations < min_observations → UNKNOWN
    min_observations: int = 10


# ---------------------------------------------------------------------------
# Input record
# ---------------------------------------------------------------------------

@dataclass
class ReadinessInput:
    """All evidence required to evaluate asset readiness.

    Optional fields reflect the reality that some data may be unavailable.
    The engine must handle None values gracefully and produce UNKNOWN where
    evidence is genuinely absent.

    Attributes:
        asset_id:               Opaque identifier (for logging).
        asset_code:             Human-readable code (e.g. "AH-64-02").
        evaluated_at:           Timestamp of this evaluation.

        -- Maintenance state --
        maintenance_status:     Current lifecycle state.
        has_blocking_work_order: True if any open work order has blocking=True.
        blocking_work_order_ids: IDs of blocking work orders.
        hours_since_last_maintenance: Hours since last completed maintenance event.
        maintenance_overdue_hours: Hours the scheduled maintenance is overdue
                                   (0.0 = on time, >0 = overdue).
        maintenance_is_critical:    Whether the overdue maintenance task is critical.

        -- Component state --
        component_states:       Map of component_code → ComponentState.
        critical_components:    Set of component codes that are safety-critical.

        -- ML predictions --
        rul_hours:              Estimated remaining useful life (hours).
        rul_lower:              Lower bound of RUL confidence interval.
        rul_upper:              Upper bound of RUL confidence interval.
        failure_probability:    Probability of failure within the mission window.
        anomaly_score:          Unsupervised anomaly score (0–1).
        prediction_confidence:  Model output confidence (0–1).
        observation_count:      Number of telemetry observations used.

        -- Telemetry freshness --
        hours_since_last_reading:   Hours since the most recent sensor reading.
        stale_sensor_codes:         Sensor codes whose last reading exceeds stale_hours.
        fault_sensor_codes:         Sensor codes reporting a hardware fault.
        drifting_sensor_codes:      Sensor codes showing drift beyond nominal range.

        -- Mission context --
        mission_duration_hours: Duration of the requested mission in hours.
        mission_id:             Optional mission identifier.
    """

    asset_id: str
    asset_code: str
    evaluated_at: datetime

    # Maintenance
    maintenance_status: MaintenanceStatus = MaintenanceStatus.OPERATIONAL
    has_blocking_work_order: bool = False
    blocking_work_order_ids: list[str] = field(default_factory=list)
    hours_since_last_maintenance: float | None = None
    maintenance_overdue_hours: float = 0.0
    maintenance_is_critical: bool = False

    # Component state
    component_states: dict[str, ComponentState] = field(default_factory=dict)
    critical_components: set[str] = field(default_factory=set)

    # ML predictions — None means "not available"
    rul_hours: float | None = None
    rul_lower: float | None = None
    rul_upper: float | None = None
    failure_probability: float | None = None
    anomaly_score: float | None = None
    prediction_confidence: float | None = None
    observation_count: int | None = None

    # Telemetry freshness
    hours_since_last_reading: float | None = None
    stale_sensor_codes: list[str] = field(default_factory=list)
    fault_sensor_codes: list[str] = field(default_factory=list)
    drifting_sensor_codes: list[str] = field(default_factory=list)

    # Mission context
    mission_duration_hours: float = 0.0
    mission_id: str | None = None


# ---------------------------------------------------------------------------
# Output record
# ---------------------------------------------------------------------------

@dataclass
class ReadinessOutput:
    """The result of a single readiness evaluation.

    Attributes:
        status:               Final classification.
        primary_reason:       The highest-priority reason code that determined status.
        contributing_factors: All factors that were considered, in priority order.
        confidence:           Overall confidence in this classification (0–1).
        evaluated_at:         Timestamp of evaluation.
        asset_id:             From the input record.
        asset_code:           From the input record.
        mission_id:           From the input record.
        thresholds_used:      Snapshot of the thresholds in effect (for auditability).
    """

    status: ReadinessStatus
    primary_reason: ReasonCode
    contributing_factors: list[ContributingFactor]
    confidence: float
    evaluated_at: datetime
    asset_id: str
    asset_code: str
    mission_id: str | None
    thresholds_used: ReadinessThresholds
