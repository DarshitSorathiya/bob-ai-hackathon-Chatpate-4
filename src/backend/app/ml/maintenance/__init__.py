"""
Maintenance Prioritization Engine.

Combines:
  - Failure risk (ML probability)
  - Remaining useful life
  - Mission proximity (hours until next mission)
  - Asset criticality
  - Component criticality
  - Safety classification
  - Current maintenance state
  - Estimated downtime cost

Produces a ranked, explainable maintenance work queue.

No LLM, no randomness, no external I/O.

Public surface:
    MaintenancePrioritizer    — main entry point
    MaintenanceItem           — input record for one maintenance candidate
    PrioritizedItem           — output record with score and evidence
    MaintenanceQueue          — ordered result set
    UrgencyLevel              — IMMEDIATE | URGENT | SCHEDULED | ROUTINE | DEFERRED
"""

from app.ml.maintenance.prioritizer import MaintenancePrioritizer
from app.ml.maintenance.models import (
    AssetCriticality,
    ComponentCriticality,
    MaintenanceItem,
    MaintenanceQueue,
    MaintenanceState,
    PrioritizedItem,
    SafetyClassification,
    UrgencyLevel,
)

__all__ = [
    "MaintenancePrioritizer",
    "MaintenanceItem",
    "PrioritizedItem",
    "MaintenanceQueue",
    "UrgencyLevel",
    "AssetCriticality",
    "ComponentCriticality",
    "SafetyClassification",
    "MaintenanceState",
]
