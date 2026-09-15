"""
Sensor model — translates latent component health into observable readings.

Causal chain (per sensor per timestep):
  1. Compute ideal baseline from sensor spec and operating condition.
  2. Add degradation-coupled signal shift (health → signal change).
  3. Apply Gaussian sensor noise.
  4. Apply active sensor fault (if injected).
  5. Return observed value (may be None for missing/dropout).

Sensor faults are stateful — they track how many steps remain active.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from app.ml.simulator.config import SensorSpec
from app.ml.simulator.environment import OperatingCondition, sensor_baseline_offset


# ─── Sensor fault types ────────────────────────────────────────────────────────


class SensorFaultType(str, Enum):
    NONE              = "NONE"
    MISSING           = "MISSING"           # dropped reading
    STALE             = "STALE"             # repeats last value
    STUCK             = "STUCK"             # fixed constant
    OUTLIER           = "OUTLIER"           # single spike (cleared next step)
    DRIFT             = "DRIFT"             # additive drift unrelated to health
    DUPLICATE         = "DUPLICATE"         # two rows with same timestamp
    SENSOR_FAILURE    = "SENSOR_FAILURE"    # total dropout


# ─── Active fault state ────────────────────────────────────────────────────────


@dataclass
class ActiveFault:
    """State of a currently active sensor fault."""

    fault_type: SensorFaultType
    remaining_steps: int            # -1 = permanent until cleared
    stuck_value: float | None = None
    drift_accumulated: float = 0.0
    drift_rate: float = 0.0


# ─── Sensor state (mutable, per timestep) ─────────────────────────────────────


@dataclass
class SensorState:
    """Mutable runtime state for one sensor."""

    sensor_id: str
    spec: SensorSpec
    last_value: float | None = None
    active_fault: ActiveFault | None = None
    duplicate_pending: bool = False   # emit a duplicate next step

    def has_fault(self) -> bool:
        return self.active_fault is not None

    def fault_type(self) -> SensorFaultType:
        if self.active_fault is None:
            return SensorFaultType.NONE
        return self.active_fault.fault_type


# ─── Ideal signal computation ─────────────────────────────────────────────────


def compute_ideal_signal(
    spec: SensorSpec,
    health: float,
    condition: OperatingCondition,
) -> float:
    """Compute the noiseless physical signal value.

    Parameters
    ----------
    spec:
        Sensor specification (nominal range, degradation sensitivity).
    health:
        Latent component health ∈ [0, 1].
    condition:
        Current operating condition (shifts baseline).

    Returns
    -------
    float
        Ideal physical reading before noise or faults.
    """
    nominal_mid = (spec.nominal_min + spec.nominal_max) / 2.0
    nominal_range = spec.nominal_max - spec.nominal_min

    # Condition baseline shift
    cond_offset = sensor_baseline_offset(condition, spec.sensor_type)
    baseline = nominal_mid + cond_offset * nominal_range

    # Degradation-coupled shift: degradation_sensitivity * (1 - health)
    # For sensors that rise on degradation (direction=+1): vibration, temperature
    # For sensors that fall on degradation (direction=-1): pressure
    health_loss = 1.0 - health
    degradation_shift = spec.degradation_sensitivity * health_loss * spec.degradation_direction

    ideal = baseline + degradation_shift
    return float(np.clip(ideal, spec.critical_min, spec.critical_max))


# ─── Noise injection ──────────────────────────────────────────────────────────


def add_sensor_noise(
    ideal: float,
    spec: SensorSpec,
    rng: np.random.Generator,
) -> float:
    """Add Gaussian sensor noise to an ideal signal."""
    noisy = ideal + rng.normal(0.0, spec.noise_sigma)
    return float(np.clip(noisy, spec.critical_min, spec.critical_max))


# ─── Fault application ────────────────────────────────────────────────────────


def apply_fault(
    state: SensorState,
    noisy_value: float,
    rng: np.random.Generator,
) -> tuple[float | None, bool]:
    """Apply the active fault to a noisy reading.

    Returns
    -------
    (observed_value, is_duplicate)
        observed_value = None means the reading is missing (dropped).
        is_duplicate = True means emit this row twice with the same timestamp.
    """
    if state.active_fault is None:
        return noisy_value, state.duplicate_pending

    fault = state.active_fault

    if fault.fault_type == SensorFaultType.MISSING:
        return None, False

    if fault.fault_type == SensorFaultType.SENSOR_FAILURE:
        return None, False

    if fault.fault_type == SensorFaultType.STALE:
        val = state.last_value if state.last_value is not None else noisy_value
        return val, False

    if fault.fault_type == SensorFaultType.STUCK:
        val = fault.stuck_value if fault.stuck_value is not None else noisy_value
        # Freeze stuck value on first application
        if fault.stuck_value is None:
            fault.stuck_value = noisy_value
        return fault.stuck_value, False

    if fault.fault_type == SensorFaultType.OUTLIER:
        # One-shot spike — clear after this step
        spec = state.spec
        spike = rng.normal(0.0, spec.noise_sigma * 5.0)
        spiked = float(np.clip(noisy_value + spike, spec.critical_min, spec.critical_max))
        fault.remaining_steps = 0  # will be cleared by advance_fault
        return spiked, False

    if fault.fault_type == SensorFaultType.DRIFT:
        fault.drift_accumulated += fault.drift_rate
        drifted = noisy_value + fault.drift_accumulated
        spec = state.spec
        return float(np.clip(drifted, spec.critical_min, spec.critical_max)), False

    if fault.fault_type == SensorFaultType.DUPLICATE:
        return noisy_value, True

    return noisy_value, False


def advance_fault(state: SensorState) -> None:
    """Decrement fault counter; clear the fault if it has expired."""
    if state.active_fault is None:
        return
    if state.active_fault.remaining_steps > 0:
        state.active_fault.remaining_steps -= 1
    if state.active_fault.remaining_steps == 0:
        state.active_fault = None
    state.duplicate_pending = False


# ─── Full sensor observation step ─────────────────────────────────────────────


def observe(
    state: SensorState,
    health: float,
    condition: OperatingCondition,
    rng: np.random.Generator,
) -> tuple[float | None, bool, SensorFaultType]:
    """Produce one observable reading from the sensor.

    Parameters
    ----------
    state:
        Mutable sensor state (updated in-place).
    health:
        Latent component health.
    condition:
        Current operating condition.
    rng:
        Sensor-specific Generator.

    Returns
    -------
    (value, is_duplicate, active_fault_type)
        value = None when reading is missing/dropped.
        is_duplicate = True when this reading should be emitted twice.
        active_fault_type = the fault that was active during this step.
    """
    ideal = compute_ideal_signal(state.spec, health, condition)
    noisy = add_sensor_noise(ideal, state.spec, rng)

    fault_type = state.fault_type()
    value, is_dup = apply_fault(state, noisy, rng)

    if value is not None:
        state.last_value = value

    advance_fault(state)

    return value, is_dup, fault_type
