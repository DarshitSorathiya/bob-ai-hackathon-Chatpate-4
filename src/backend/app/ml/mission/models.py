"""
Data models for the Mission Engine.

All models are pure dataclasses / enums — no database I/O.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class MissionRiskLevel(str, enum.Enum):
    """Overall risk classification for a mission.

    LOW       — All required capabilities are met with READY assets.
    MODERATE  — Some assets are AT_RISK; mission can proceed with monitoring.
    HIGH      — Readiness gaps or NOT_READY assets threaten mission success.
    CRITICAL  — Mission cannot be executed safely with current assets.
    """

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MissionStatus(str, enum.Enum):
    """Planning-level status of the mission."""

    GO = "GO"               # All requirements met, risk acceptable
    GO_WITH_RISK = "GO_WITH_RISK"   # Requirements met but elevated risk
    NO_GO = "NO_GO"         # Critical gaps; mission should not proceed
    UNKNOWN = "UNKNOWN"     # Insufficient data to determine


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

@dataclass
class CapabilityRequirement:
    """A capability the mission requires and how many assets must provide it.

    Attributes:
        capability:   String identifier (e.g. "ATTACK", "RECON", "TRANSPORT").
        required_count: Minimum number of assets providing this capability.
        is_critical:  If True, failing this requirement makes the mission NO_GO.
    """

    capability: str
    required_count: int
    is_critical: bool = True


@dataclass
class AssetCapability:
    """One asset with its declared capabilities and current readiness.

    Attributes:
        asset_id:       Opaque identifier.
        asset_code:     Human-readable code.
        capabilities:   Set of capability strings this asset can provide.
        readiness_status: Current readiness (from ReadinessEngine output).
        readiness_confidence: Confidence in the readiness classification (0–1).
        primary_reason: Primary reason code from ReadinessEngine.
        rul_hours:      Remaining useful life (hours), if available.
        failure_probability: Failure probability, if available.
        is_assigned:    True if this asset is already tentatively assigned.
        assigned_mission_ids: Missions this asset is currently assigned to.
    """

    asset_id: str
    asset_code: str
    capabilities: set[str]
    readiness_status: str          # ReadinessStatus value
    readiness_confidence: float
    primary_reason: str            # ReasonCode value
    rul_hours: float | None = None
    failure_probability: float | None = None
    is_assigned: bool = False
    assigned_mission_ids: list[str] = field(default_factory=list)


@dataclass
class SubstitutionCandidate:
    """A substitute asset that could fill a readiness gap.

    Attributes:
        asset_id:         Opaque identifier.
        asset_code:       Human-readable code.
        capability:       The capability this substitution provides.
        readiness_status: Current readiness status.
        confidence:       Confidence score.
        suitability_score: Combined score (0–1) ranking this candidate.
        reason:           Why this candidate was selected.
    """

    asset_id: str
    asset_code: str
    capability: str
    readiness_status: str
    confidence: float
    suitability_score: float
    reason: str


@dataclass
class ReadinessGap:
    """An unmet capability requirement.

    Attributes:
        capability:       The capability that is short.
        required_count:   How many assets are needed.
        available_count:  How many READY assets are available.
        at_risk_count:    How many AT_RISK assets are available (partial credit).
        is_critical:      Whether this gap makes the mission NO_GO.
        substitutions:    Ranked list of substitute candidates.
    """

    capability: str
    required_count: int
    available_count: int
    at_risk_count: int
    is_critical: bool
    substitutions: list[SubstitutionCandidate] = field(default_factory=list)

    @property
    def shortage(self) -> int:
        """Number of READY assets short of requirement."""
        return max(0, self.required_count - self.available_count)

    @property
    def is_fully_met(self) -> bool:
        return self.available_count >= self.required_count

    @property
    def is_partially_met(self) -> bool:
        return not self.is_fully_met and (self.available_count + self.at_risk_count) >= self.required_count


@dataclass
class ConflictReport:
    """A scheduling conflict between an asset and one or more missions.

    Attributes:
        asset_id:           Asset that has the conflict.
        asset_code:         Human-readable code.
        conflicting_mission_ids: Missions competing for this asset.
        conflict_type:      "DOUBLE_ASSIGNED" | "MAINTENANCE_WINDOW" | "UNAVAILABLE"
        description:        Human-readable explanation.
    """

    asset_id: str
    asset_code: str
    conflicting_mission_ids: list[str]
    conflict_type: str
    description: str


@dataclass
class CapabilityReadiness:
    """Readiness summary for one capability slot."""

    capability: str
    required_count: int
    ready_assets: list[str]
    at_risk_assets: list[str]
    not_ready_assets: list[str]
    unknown_assets: list[str]


# ---------------------------------------------------------------------------
# Input / Output
# ---------------------------------------------------------------------------

@dataclass
class MissionInput:
    """All data needed to evaluate mission readiness.

    Attributes:
        mission_id:           Opaque mission identifier.
        mission_code:         Human-readable mission code.
        mission_window_hours: Duration of the mission in hours.
        start_time:           Planned mission start.
        requirements:         Capability requirements for this mission.
        assigned_assets:      Assets currently assigned, with their readiness.
        fleet_assets:         All assets in the fleet (for substitution lookup).
        evaluated_at:         Timestamp of this evaluation.
    """

    mission_id: str
    mission_code: str
    mission_window_hours: float
    start_time: datetime
    requirements: list[CapabilityRequirement]
    assigned_assets: list[AssetCapability]
    fleet_assets: list[AssetCapability]
    evaluated_at: datetime


@dataclass
class MissionOutput:
    """Result of a mission readiness evaluation.

    Attributes:
        mission_id:           From the input.
        mission_code:         From the input.
        status:               Overall GO / GO_WITH_RISK / NO_GO / UNKNOWN.
        risk_level:           LOW / MODERATE / HIGH / CRITICAL.
        risk_score:           Numeric risk score (0.0 = no risk, 1.0 = maximum).
        capability_readiness: Per-capability breakdown.
        gaps:                 All readiness gaps (empty = no gaps).
        conflicts:            Scheduling conflicts detected.
        evaluated_at:         From the input.
        summary:              Human-readable summary string.
        contributing_factors: Ordered list of (reason, description) pairs.
    """

    mission_id: str
    mission_code: str
    status: MissionStatus
    risk_level: MissionRiskLevel
    risk_score: float
    capability_readiness: list[CapabilityReadiness]
    gaps: list[ReadinessGap]
    conflicts: list[ConflictReport]
    evaluated_at: datetime
    summary: str
    contributing_factors: list[tuple[str, str]]
