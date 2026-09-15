"""
Explainable Readiness Engine — deterministic, rule-based, fully auditable.

No ML model is involved in the readiness decision.  ML predictions
(RUL, failure probability, anomaly score) are *inputs* to the rules;
the rules themselves are hard-coded policy that a human can inspect
and override.

Public surface:
    ReadinessEngine          — main entry point
    ReadinessInput           — typed input record
    ReadinessOutput          — typed output record
    ReadinessStatus          — READY | AT_RISK | NOT_READY | UNKNOWN
    ReasonCode               — enumerated reason codes
    ContributingFactor       — structured evidence item
    ReadinessThresholds      — tunable cut-offs (with safe defaults)
"""

from app.ml.readiness.engine import ReadinessEngine
from app.ml.readiness.models import (
    ComponentState,
    ContributingFactor,
    MaintenanceStatus,
    ReadinessInput,
    ReadinessOutput,
    ReadinessStatus,
    ReadinessThresholds,
    ReasonCode,
)

__all__ = [
    "ReadinessEngine",
    "ReadinessInput",
    "ReadinessOutput",
    "ReadinessStatus",
    "ReasonCode",
    "ContributingFactor",
    "ReadinessThresholds",
    "ComponentState",
    "MaintenanceStatus",
]
