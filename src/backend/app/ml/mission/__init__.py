"""
Mission Engine — deterministic mission readiness aggregation.

Computes:
  - Assigned asset readiness per required capability
  - Readiness gaps (unfulfilled capability requirements)
  - Substitution candidates for gaps
  - Mission-window risk score
  - Mission impact classification
  - Scheduling conflicts between assets and missions

No LLM, no randomness, no external I/O.

Public surface:
    MissionEngine         — main entry point
    MissionInput          — typed input record
    MissionOutput         — typed output record
    CapabilityRequirement — a required capability with count
    AssetCapability       — an asset with its capabilities and readiness
    ReadinessGap          — an unmet requirement with substitution candidates
    MissionRiskLevel      — LOW | MODERATE | HIGH | CRITICAL
    ConflictReport        — scheduling conflict between an asset and missions
"""

from app.ml.mission.engine import MissionEngine
from app.ml.mission.models import (
    AssetCapability,
    CapabilityRequirement,
    ConflictReport,
    MissionInput,
    MissionOutput,
    MissionRiskLevel,
    MissionStatus,
    ReadinessGap,
    SubstitutionCandidate,
)

__all__ = [
    "MissionEngine",
    "MissionInput",
    "MissionOutput",
    "CapabilityRequirement",
    "AssetCapability",
    "ReadinessGap",
    "SubstitutionCandidate",
    "MissionRiskLevel",
    "MissionStatus",
    "ConflictReport",
]
