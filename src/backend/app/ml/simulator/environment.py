"""
Operating conditions and environmental variation for the fleet simulator.

Operating conditions define the context in which an asset is operating at
each timestep. They affect:
  1. Degradation rate (via condition_mult in DegradationParams).
  2. Sensor baselines (e.g. temperature is higher during TAKEOFF).
  3. Mission feasibility checks.

Each asset follows a condition schedule that transitions through states
based on its mission assignments and daily operational pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from app.ml.simulator.config import DegradationParams


# ─── Operating conditions ─────────────────────────────────────────────────────


class OperatingCondition(str, Enum):
    IDLE                = "IDLE"
    CRUISE              = "CRUISE"
    TAKEOFF             = "TAKEOFF"
    COMBAT              = "COMBAT"
    MAINTENANCE_GROUND  = "MAINTENANCE_GROUND"


# Sensor baseline scaling per condition (multiplied on top of nominal midpoint)
# Format: {sensor_type: additive_offset_fraction}  (fraction of nominal range)
CONDITION_SENSOR_OFFSETS: dict[str, dict[str, float]] = {
    "IDLE": {
        "VIBRATION_RMS":    -0.20,
        "TEMP_ENGINE":      -0.30,
        "PRESSURE_HYD":     -0.10,
        "FAN_SPEED_RPM":    -0.25,
        "BEARING_VIBRATION":-0.15,
        "BEARING_TEMP":     -0.20,
        "OIL_PRESSURE":     -0.10,
    },
    "CRUISE": {
        "VIBRATION_RMS":     0.00,
        "TEMP_ENGINE":       0.00,
        "PRESSURE_HYD":      0.00,
        "FAN_SPEED_RPM":     0.00,
        "BEARING_VIBRATION": 0.00,
        "BEARING_TEMP":      0.00,
        "OIL_PRESSURE":      0.00,
    },
    "TAKEOFF": {
        "VIBRATION_RMS":     0.30,
        "TEMP_ENGINE":       0.35,
        "PRESSURE_HYD":      0.20,
        "FAN_SPEED_RPM":     0.30,
        "BEARING_VIBRATION": 0.25,
        "BEARING_TEMP":      0.30,
        "OIL_PRESSURE":      0.15,
    },
    "COMBAT": {
        "VIBRATION_RMS":     0.45,
        "TEMP_ENGINE":       0.50,
        "PRESSURE_HYD":      0.30,
        "FAN_SPEED_RPM":     0.40,
        "BEARING_VIBRATION": 0.40,
        "BEARING_TEMP":      0.45,
        "OIL_PRESSURE":      0.20,
    },
    "MAINTENANCE_GROUND": {
        "VIBRATION_RMS":    -0.50,
        "TEMP_ENGINE":      -0.60,
        "PRESSURE_HYD":      0.00,
        "FAN_SPEED_RPM":    -0.80,
        "BEARING_VIBRATION":-0.50,
        "BEARING_TEMP":     -0.40,
        "OIL_PRESSURE":     -0.20,
    },
}


def condition_multiplier(condition: OperatingCondition, params: DegradationParams) -> float:
    """Return the degradation rate multiplier for the given operating condition."""
    return params.condition_multipliers.get(condition.value, 1.0)


def sensor_baseline_offset(condition: OperatingCondition, sensor_type: str) -> float:
    """Return the additive offset fraction for a sensor under a given condition.

    The offset is a fraction of the sensor's nominal range (nominal_max - nominal_min).
    """
    return CONDITION_SENSOR_OFFSETS.get(condition.value, {}).get(sensor_type, 0.0)


# ─── Condition scheduler ──────────────────────────────────────────────────────


# Typical daily operating profile (hours in each condition per 24h)
_DEFAULT_DAILY_PROFILE: dict[OperatingCondition, float] = {
    OperatingCondition.IDLE:               8.0,
    OperatingCondition.CRUISE:            12.0,
    OperatingCondition.TAKEOFF:            2.0,
    OperatingCondition.COMBAT:             2.0,
    OperatingCondition.MAINTENANCE_GROUND: 0.0,  # inserted by maintenance model
}


@dataclass
class ConditionSchedule:
    """Pre-computed sequence of operating conditions for one asset."""

    conditions: list[OperatingCondition]  # one entry per timestep

    def __len__(self) -> int:
        return len(self.conditions)

    def __getitem__(self, idx: int) -> OperatingCondition:
        return self.conditions[idx]


def build_condition_schedule(
    n_timesteps: int,
    timestep_hours: float,
    rng: np.random.Generator,
    usage_intensity: float = 1.0,
) -> ConditionSchedule:
    """Build a stochastic operating condition schedule for one asset.

    Conditions are drawn from a Markov-like transition based on the daily
    profile, scaled by the asset's usage intensity.

    Parameters
    ----------
    n_timesteps:
        Total number of timesteps in the simulation.
    timestep_hours:
        Hours per timestep.
    rng:
        Asset-specific Generator.
    usage_intensity:
        Scale factor ∈ [0.5, 1.5] — higher = more COMBAT/TAKEOFF, less IDLE.

    Returns
    -------
    ConditionSchedule
    """
    # Build probability weights adjusted for usage intensity
    base_weights = {
        OperatingCondition.IDLE:    max(0.1, 0.33 - 0.15 * (usage_intensity - 1.0)),
        OperatingCondition.CRUISE:  0.50,
        OperatingCondition.TAKEOFF: min(0.25, 0.08 + 0.06 * usage_intensity),
        OperatingCondition.COMBAT:  min(0.20, 0.08 + 0.05 * usage_intensity),
        OperatingCondition.MAINTENANCE_GROUND: 0.0,  # set externally
    }
    conditions_list = list(base_weights.keys())
    weights = np.array([base_weights[c] for c in conditions_list])
    weights /= weights.sum()

    indices = rng.choice(len(conditions_list), size=n_timesteps, p=weights)
    schedule = [conditions_list[i] for i in indices]
    return ConditionSchedule(conditions=schedule)
