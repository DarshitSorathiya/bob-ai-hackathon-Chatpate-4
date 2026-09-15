"""
Truth layer — latent health state and ground truth records.

The TruthLayer is the authoritative source of simulated reality.
It holds per-component health trajectories, failure timestamps, and
true RUL values.

ANTI-LEAKAGE CONTRACT
---------------------
TruthLayer data MUST NEVER be added to the observable telemetry tables
(assets, telemetry, telemetry_quality, data_quality_events, maintenance_events,
work_orders, missions, mission_assignments).

The only legitimate use of TruthLayer output is:
  1. Computing training labels in the export layer (export.py).
  2. Simulator self-validation (validate.py).

The export layer is responsible for enforcing this boundary.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ─── Truth records ────────────────────────────────────────────────────────────


@dataclass
class ComponentTruth:
    """Complete latent history for one component."""

    component_id: str
    asset_id: str
    component_type: str
    archetype: str                      # DegradationArchetype name
    degradation_multiplier: float       # fleet heterogeneity factor

    # Per-timestep history (parallel lists, one entry per sim timestep)
    timestamps: list[datetime] = field(default_factory=list)
    health: list[float] = field(default_factory=list)   # [0, 1]
    true_rul: list[float | None] = field(default_factory=list)

    # Failure event (None if censored)
    failure_timestamp: datetime | None = None
    failure_type: str | None = None

    # Maintenance event timestamps (used to verify recovery in validation)
    maintenance_timestamps: list[datetime] = field(default_factory=list)

    def is_censored(self) -> bool:
        return self.failure_timestamp is None

    def failed(self) -> bool:
        return self.failure_timestamp is not None

    def health_at(self, ts: datetime) -> float | None:
        """Return health at the closest recorded timestamp, or None."""
        for i, t in enumerate(self.timestamps):
            if t >= ts:
                return self.health[i]
        return None


@dataclass
class AssetTruth:
    """Aggregated truth for one asset (across all components)."""

    asset_id: str
    asset_code: str
    asset_type: str
    usage_intensity: float
    sensor_quality: float           # fleet heterogeneity factor

    component_truths: dict[str, ComponentTruth] = field(default_factory=dict)

    def any_failed(self) -> bool:
        return any(ct.failed() for ct in self.component_truths.values())

    def first_failure(self) -> datetime | None:
        failures = [
            ct.failure_timestamp
            for ct in self.component_truths.values()
            if ct.failure_timestamp is not None
        ]
        return min(failures) if failures else None

    def min_health_at(self, ts: datetime) -> float:
        healths = [
            ct.health_at(ts)
            for ct in self.component_truths.values()
        ]
        valid = [h for h in healths if h is not None]
        return min(valid) if valid else 1.0


@dataclass
class FleetTruth:
    """Complete ground-truth state of the entire simulated fleet."""

    seed: int
    n_assets: int
    sim_days: int
    timestep_hours: float

    asset_truths: dict[str, AssetTruth] = field(default_factory=dict)

    def component_truths(self) -> list[ComponentTruth]:
        """Flat list of all component truths across all assets."""
        return [
            ct
            for at in self.asset_truths.values()
            for ct in at.component_truths.values()
        ]

    def failure_count(self) -> int:
        return sum(1 for ct in self.component_truths() if ct.failed())

    def censored_count(self) -> int:
        return sum(1 for ct in self.component_truths() if ct.is_censored())

    def summary(self) -> dict:
        cts = self.component_truths()
        healthy_final = [ct.health[-1] for ct in cts if ct.health]
        return {
            "n_assets": self.n_assets,
            "n_components": len(cts),
            "n_failed": self.failure_count(),
            "n_censored": self.censored_count(),
            "mean_final_health": float(sum(healthy_final) / len(healthy_final))
            if healthy_final else 0.0,
            "min_final_health": float(min(healthy_final)) if healthy_final else 0.0,
        }
