"""
Controlled edge case injectors for the fleet simulator.

Each injector is responsible for one class of observable anomaly.
Injectors operate on the sensor state or asset state — they do NOT
modify the truth layer (health, true RUL, or failure records).

All injectors are deterministic given their per-label RNG stream.
Each edge case is tagged with an EdgeCaseTag so the validation suite
can verify it was produced.

Edge cases injected:
  1.  MISSING_TELEMETRY          — 40% reading dropout on one sensor of one asset
  2.  STALE_TELEMETRY            — sensor repeats last value for 30 steps
  3.  STUCK_SENSOR               — constant reading for 60 steps
  4.  OUTLIER                    — isolated spike (cleared next step)
  5.  DRIFT                      — additive drift unrelated to degradation
  6.  DUPLICATE_TIMESTAMP        — two rows with identical timestamp
  7.  SENSOR_FAILURE             — total dropout for 100 steps
  8.  COMPONENT_DEGRADATION      — guaranteed GRADUAL archetype component
  9.  UNDER_MAINTENANCE          — asset forced into maintenance window
  10. OVERDUE_MAINTENANCE        — MTBF exceeded without maintenance trigger
  11. MISSION_CONFLICT           — mission assigned despite RUL < duration
  12. HIGH_ANOMALY_LOW_FAILURE   — temporary health dip then recovery
  13. POOR_QUALITY_GENUINE_DEG   — simultaneous high fault rate + real degradation
  14. RUL_SHORTER_THAN_MISSION   — alias for MISSION_CONFLICT (explicit label)
  15. INSUFFICIENT_DATA          — asset with <10 total observations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from app.ml.simulator.config import EdgeCaseParams
from app.ml.simulator.sensor import (
    ActiveFault,
    SensorFaultType,
    SensorState,
)


# ─── Edge case tags ───────────────────────────────────────────────────────────


class EdgeCaseTag(str, Enum):
    MISSING_TELEMETRY           = "missing_telemetry"
    STALE_TELEMETRY             = "stale_telemetry"
    STUCK_SENSOR                = "stuck_sensor"
    OUTLIER                     = "outlier"
    DRIFT                       = "drift"
    DUPLICATE_TIMESTAMP         = "duplicate_timestamp"
    SENSOR_FAILURE              = "sensor_failure"
    COMPONENT_DEGRADATION       = "component_degradation"
    UNDER_MAINTENANCE           = "under_maintenance"
    OVERDUE_MAINTENANCE         = "overdue_maintenance"
    MISSION_CONFLICT            = "mission_conflict"
    HIGH_ANOMALY_LOW_FAILURE    = "high_anomaly_low_failure"
    POOR_QUALITY_GENUINE_DEG    = "poor_quality_genuine_degradation"
    RUL_SHORTER_THAN_MISSION    = "rul_shorter_than_mission"
    INSUFFICIENT_DATA           = "insufficient_data"


# ─── Injection plan (built once before simulation) ────────────────────────────


@dataclass
class EdgeCaseInjectionPlan:
    """Which edge cases apply to which assets/sensors.

    Built by EdgeCasePlanner.build() before the main simulation loop.
    Consumed by the engine during simulation.
    """

    # Map: asset_id → set of EdgeCaseTags applied to that asset
    asset_tags: dict[str, set[EdgeCaseTag]] = field(default_factory=dict)

    # Map: (asset_id, sensor_id) → SensorFaultType + params
    sensor_faults: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    # Set of asset_ids that should have <insufficient_data_max_steps observations
    insufficient_data_assets: set[str] = field(default_factory=set)

    # Set of (asset_id, component_id) forced to GRADUAL archetype
    forced_gradual: set[tuple[str, str]] = field(default_factory=set)

    # asset_ids to force into overdue maintenance
    overdue_maintenance_assets: set[str] = field(default_factory=set)

    # (asset_id, component_id) that get a temporary health dip (high anomaly low failure)
    health_dip_components: set[tuple[str, str]] = field(default_factory=set)
    health_dip_step: dict[tuple[str, str], int] = field(default_factory=dict)

    # asset_ids that will get a mission_conflict scheduled
    mission_conflict_assets: set[str] = field(default_factory=set)

    # All injected tags (for validation)
    all_injected_tags: set[EdgeCaseTag] = field(default_factory=set)


# ─── Planner ──────────────────────────────────────────────────────────────────


class EdgeCasePlanner:
    """Assigns edge cases to specific assets/sensors before simulation runs."""

    def __init__(
        self,
        params: EdgeCaseParams,
        asset_ids: list[str],
        sensor_map: dict[str, list[str]],   # asset_id → [sensor_id, ...]
        component_map: dict[str, list[str]], # asset_id → [component_id, ...]
        rng_manager: Any,                    # RNGManager
    ) -> None:
        self._params = params
        self._asset_ids = asset_ids
        self._sensor_map = sensor_map
        self._component_map = component_map
        self._rng = rng_manager

    def build(self) -> EdgeCaseInjectionPlan:
        """Assign edge cases to assets and sensors.

        For the tiny profile (≤10 assets), at least one of each enabled
        edge case type is guaranteed. For larger profiles, they are sampled
        probabilistically.
        """
        plan = EdgeCaseInjectionPlan()
        params = self._params
        n = len(self._asset_ids)

        def pick_asset(label: str) -> str:
            rng = self._rng.edge_case(label)
            return self._asset_ids[int(rng.integers(0, n))]

        def pick_sensor(asset_id: str, label: str) -> str | None:
            sensors = self._sensor_map.get(asset_id, [])
            if not sensors:
                return None
            rng = self._rng.edge_case(label + "_sensor")
            return sensors[int(rng.integers(0, len(sensors)))]

        def pick_component(asset_id: str, label: str) -> str | None:
            comps = self._component_map.get(asset_id, [])
            if not comps:
                return None
            rng = self._rng.edge_case(label + "_comp")
            return comps[int(rng.integers(0, len(comps)))]

        def tag(asset_id: str, tag: EdgeCaseTag) -> None:
            plan.asset_tags.setdefault(asset_id, set()).add(tag)
            plan.all_injected_tags.add(tag)

        def fault(asset_id: str, sensor_id: str, fault_type: str, **kwargs: Any) -> None:
            plan.sensor_faults[(asset_id, sensor_id)] = {"fault_type": fault_type, **kwargs}

        # 1. MISSING TELEMETRY
        if params.inject_missing_telemetry and n >= 1:
            a = pick_asset("missing")
            s = pick_sensor(a, "missing")
            if s:
                fault(a, s, "MISSING", missing_fraction=params.missing_fraction)
                tag(a, EdgeCaseTag.MISSING_TELEMETRY)

        # 2. STALE TELEMETRY
        if params.inject_stale_telemetry and n >= 2:
            a = pick_asset("stale")
            s = pick_sensor(a, "stale")
            if s:
                fault(a, s, "STALE", duration_steps=params.stale_duration_steps)
                tag(a, EdgeCaseTag.STALE_TELEMETRY)

        # 3. STUCK SENSOR
        if params.inject_stuck_sensor and n >= 3:
            a = pick_asset("stuck")
            s = pick_sensor(a, "stuck")
            if s:
                fault(a, s, "STUCK", duration_steps=params.stuck_duration_steps)
                tag(a, EdgeCaseTag.STUCK_SENSOR)

        # 4. OUTLIER
        if params.inject_outlier and n >= 1:
            a = pick_asset("outlier")
            s = pick_sensor(a, "outlier")
            if s:
                fault(a, s, "OUTLIER", sigma_mult=params.outlier_sigma_multiplier)
                tag(a, EdgeCaseTag.OUTLIER)

        # 5. DRIFT
        if params.inject_drift and n >= 2:
            a = pick_asset("drift")
            s = pick_sensor(a, "drift")
            if s:
                fault(a, s, "DRIFT", drift_rate=params.drift_rate_per_step)
                tag(a, EdgeCaseTag.DRIFT)

        # 6. DUPLICATE TIMESTAMP
        if params.inject_duplicate_timestamp and n >= 1:
            a = pick_asset("dup")
            s = pick_sensor(a, "dup")
            if s:
                fault(a, s, "DUPLICATE", duration_steps=1)
                tag(a, EdgeCaseTag.DUPLICATE_TIMESTAMP)

        # 7. SENSOR FAILURE
        if params.inject_sensor_failure and n >= 3:
            a = pick_asset("sfail")
            s = pick_sensor(a, "sfail")
            if s:
                fault(a, s, "SENSOR_FAILURE", duration_steps=params.sensor_failure_duration_steps)
                tag(a, EdgeCaseTag.SENSOR_FAILURE)

        # 8. COMPONENT DEGRADATION (guaranteed GRADUAL)
        a = pick_asset("degradation")
        c = pick_component(a, "degradation")
        if c:
            plan.forced_gradual.add((a, c))
            tag(a, EdgeCaseTag.COMPONENT_DEGRADATION)

        # 9. UNDER MAINTENANCE — handled at assembly time (forced early maintenance)

        # 10. OVERDUE MAINTENANCE
        if params.inject_overdue_maintenance and n >= 4:
            a = pick_asset("overdue")
            plan.overdue_maintenance_assets.add(a)
            tag(a, EdgeCaseTag.OVERDUE_MAINTENANCE)

        # 11. MISSION CONFLICT
        if params.inject_mission_conflict and n >= 2:
            a = pick_asset("mission_conflict")
            plan.mission_conflict_assets.add(a)
            tag(a, EdgeCaseTag.MISSION_CONFLICT)
            tag(a, EdgeCaseTag.RUL_SHORTER_THAN_MISSION)

        # 12. HIGH ANOMALY LOW FAILURE (temporary dip)
        if params.inject_high_anomaly_low_failure and n >= 2:
            a = pick_asset("high_anomaly")
            c = pick_component(a, "high_anomaly")
            if c:
                rng = self._rng.edge_case("high_anomaly_step")
                # Schedule dip at 20–40% into the simulation
                from app.ml.simulator.config import SimulatorConfig
                plan.health_dip_components.add((a, c))
                # step will be set by engine based on total steps
                plan.health_dip_step[(a, c)] = -1  # -1 = calculate at engine init
                tag(a, EdgeCaseTag.HIGH_ANOMALY_LOW_FAILURE)

        # 13. POOR QUALITY + GENUINE DEGRADATION
        if params.inject_poor_quality_genuine_degradation and n >= 3:
            a = pick_asset("poor_quality")
            s = pick_sensor(a, "poor_quality")
            c = pick_component(a, "poor_quality")
            if s and c:
                fault(a, s, "MISSING", missing_fraction=0.5)  # 50% missing
                plan.forced_gradual.add((a, c))
                tag(a, EdgeCaseTag.POOR_QUALITY_GENUINE_DEG)

        # 15. INSUFFICIENT DATA
        if params.inject_insufficient_data and n >= 5:
            a = pick_asset("insuf")
            plan.insufficient_data_assets.add(a)
            tag(a, EdgeCaseTag.INSUFFICIENT_DATA)

        return plan
