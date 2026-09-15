"""
Data models for the Maintenance Prioritization Engine.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class UrgencyLevel(str, enum.Enum):
    """Urgency classification for a maintenance item.

    IMMEDIATE  — Must be addressed within 24 hours; do not assign to missions.
    URGENT     — Address within 72 hours; mission assignment at commander discretion.
    SCHEDULED  — Address within the next scheduled maintenance window.
    ROUTINE    — Address at next convenient opportunity.
    DEFERRED   — Low priority; can be deferred beyond next window.
    """

    IMMEDIATE = "IMMEDIATE"
    URGENT = "URGENT"
    SCHEDULED = "SCHEDULED"
    ROUTINE = "ROUTINE"
    DEFERRED = "DEFERRED"


class AssetCriticality(str, enum.Enum):
    """How critical the asset is to overall fleet capability."""

    CRITICAL = "CRITICAL"       # Loss significantly degrades fleet capability
    HIGH = "HIGH"               # Important but substitutable
    MEDIUM = "MEDIUM"           # Secondary capability
    LOW = "LOW"                 # Non-essential


class ComponentCriticality(str, enum.Enum):
    """How critical the component is to asset airworthiness/operability."""

    SAFETY_CRITICAL = "SAFETY_CRITICAL"   # Failure causes immediate safety hazard
    MISSION_CRITICAL = "MISSION_CRITICAL" # Failure prevents mission completion
    OPERATIONAL = "OPERATIONAL"           # Degrades but does not prevent operation
    NON_ESSENTIAL = "NON_ESSENTIAL"       # Comfort, convenience, secondary


class SafetyClassification(str, enum.Enum):
    """Safety implication of deferring this maintenance item."""

    AIRWORTHINESS_LIMITING = "AIRWORTHINESS_LIMITING"   # Aircraft cannot fly
    SAFETY_OF_FLIGHT = "SAFETY_OF_FLIGHT"               # Crash hazard
    SAFETY_RISK = "SAFETY_RISK"                         # Elevated risk, not immediate
    NO_SAFETY_IMPLICATION = "NO_SAFETY_IMPLICATION"


class MaintenanceState(str, enum.Enum):
    """Current state of the maintenance work order."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_PARTS = "AWAITING_PARTS"
    COMPLETED = "COMPLETED"
    DEFERRED = "DEFERRED"


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

@dataclass
class MaintenanceItem:
    """One maintenance candidate to be prioritized.

    Attributes:
        item_id:                  Unique identifier (work order ID or recommendation ID).
        asset_id:                 Asset this item belongs to.
        asset_code:               Human-readable asset identifier.
        component_code:           Component requiring maintenance.
        description:              Human-readable description.

        -- Risk signals --
        failure_probability:      P(failure within mission window). None = unknown.
        rul_hours:                Remaining useful life. None = unknown.
        anomaly_score:            Anomaly severity (0–1). None = unknown.

        -- Mission proximity --
        hours_until_next_mission: Hours until the next scheduled mission.
                                  None = no mission scheduled.
        blocks_mission:           True if this item prevents mission execution.

        -- Classification --
        asset_criticality:        Fleet-level asset criticality.
        component_criticality:    Component-level criticality.
        safety_classification:    Safety implication of deferral.
        maintenance_state:        Current state of work order.

        -- Operational context --
        estimated_downtime_hours: Expected hours offline for repair.
        hours_overdue:            Hours past the scheduled maintenance date.
        last_maintenance_hours:   Asset hours at last maintenance event.
        current_asset_hours:      Current total asset operating hours.
    """

    item_id: str
    asset_id: str
    asset_code: str
    component_code: str
    description: str

    # Risk signals
    failure_probability: float | None = None
    rul_hours: float | None = None
    anomaly_score: float | None = None

    # Mission context
    hours_until_next_mission: float | None = None
    blocks_mission: bool = False

    # Classification
    asset_criticality: AssetCriticality = AssetCriticality.MEDIUM
    component_criticality: ComponentCriticality = ComponentCriticality.OPERATIONAL
    safety_classification: SafetyClassification = SafetyClassification.NO_SAFETY_IMPLICATION
    maintenance_state: MaintenanceState = MaintenanceState.OPEN

    # Operational context
    estimated_downtime_hours: float = 4.0
    hours_overdue: float = 0.0
    last_maintenance_hours: float | None = None
    current_asset_hours: float | None = None


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

@dataclass
class ScoreBreakdown:
    """Individual score components for auditability."""

    failure_risk_score: float
    rul_score: float
    mission_proximity_score: float
    asset_criticality_score: float
    component_criticality_score: float
    safety_score: float
    overdue_score: float
    total: float


@dataclass
class PrioritizedItem:
    """A maintenance item with its computed priority and evidence.

    Attributes:
        item_id:           From input.
        asset_id:          From input.
        asset_code:        From input.
        component_code:    From input.
        description:       From input.
        priority_score:    Composite score in [0, 1]; higher = more urgent.
        urgency_level:     Categorical urgency from priority_score.
        blocks_mission:    Whether this blocks mission assignment.
        score_breakdown:   Component-by-component score for auditability.
        contributing_factors: Ordered list of (reason, detail) pairs.
        recommended_action:  Human-readable recommendation string.
    """

    item_id: str
    asset_id: str
    asset_code: str
    component_code: str
    description: str
    priority_score: float
    urgency_level: UrgencyLevel
    blocks_mission: bool
    score_breakdown: ScoreBreakdown
    contributing_factors: list[tuple[str, str]]
    recommended_action: str


@dataclass
class MaintenanceQueue:
    """Ranked maintenance work queue.

    items is sorted by priority_score descending (most urgent first).
    """

    items: list[PrioritizedItem]
    evaluated_at: Any  # datetime
    total_immediate: int
    total_urgent: int
    total_scheduled: int

    @property
    def immediate_items(self) -> list[PrioritizedItem]:
        return [i for i in self.items if i.urgency_level == UrgencyLevel.IMMEDIATE]

    @property
    def mission_blocking_items(self) -> list[PrioritizedItem]:
        return [i for i in self.items if i.blocks_mission]
