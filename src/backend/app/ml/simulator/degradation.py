"""
Degradation archetypes for the fleet simulator.

Each archetype is a pure function:
  health_next = archetype(health_now, dt_hours, operating_condition, params, rng)

Health is in [0.0, 1.0]:
  1.0 = perfect condition
  0.0 = completely failed

The archetypes are informed by observed behavior in:
  - NASA C-MAPSS: quasi-linear degradation with a flat healthy phase followed
    by a steeper descent (piecewise linear RUL approximation).
  - NASA IMS bearings: kurtosis/RMS spike pattern — a long stable phase followed
    by sudden exponential rise in vibration features near failure (nonlinear).

Archetypes
----------
HEALTHY          — very slow random walk; represents assets with minimal wear.
GRADUAL          — steady linear decay; C-MAPSS-inspired engine degradation.
ACCELERATED      — fast but still monotonic; high-stress usage.
ABRUPT           — small baseline drift + rare sudden steps (stochastic failure).
NONLINEAR        — stable until a knee point, then exponential decay (IMS-inspired).
RECOVERABLE      — gradual decay that partially resets on maintenance events.
"""

from __future__ import annotations

import math
from enum import Enum

import numpy as np

from app.ml.simulator.config import DegradationParams


# ─── Archetype enum ───────────────────────────────────────────────────────────


class DegradationArchetype(str, Enum):
    HEALTHY      = "HEALTHY"
    GRADUAL      = "GRADUAL"
    ACCELERATED  = "ACCELERATED"
    ABRUPT       = "ABRUPT"
    NONLINEAR    = "NONLINEAR"
    RECOVERABLE  = "RECOVERABLE"


# Minimum health before forced failure
FAILURE_HEALTH_THRESHOLD = 0.05


# ─── Core degradation functions ───────────────────────────────────────────────


def degrade_healthy(
    health: float,
    dt_hours: float,
    condition_mult: float,
    params: DegradationParams,
    rng: np.random.Generator,
) -> float:
    """Very slow, almost imperceptible degradation with tiny stochastic jitter."""
    rate = params.healthy_rate * condition_mult
    jitter = rng.normal(0.0, rate * 0.1)
    return max(0.0, health - (rate * dt_hours + jitter))


def degrade_gradual(
    health: float,
    dt_hours: float,
    condition_mult: float,
    params: DegradationParams,
    rng: np.random.Generator,
) -> float:
    """Steady quasi-linear decay — C-MAPSS turbofan engine archetype.

    A small random component models cycle-to-cycle variability. The rate
    is approximately constant (no knee), matching the piecewise-linear
    RUL model used in C-MAPSS evaluation.
    """
    rate = params.gradual_rate * condition_mult
    noise = rng.normal(0.0, rate * 0.05)
    delta = max(0.0, rate * dt_hours + noise)
    return max(0.0, health - delta)


def degrade_accelerated(
    health: float,
    dt_hours: float,
    condition_mult: float,
    params: DegradationParams,
    rng: np.random.Generator,
) -> float:
    """Fast, monotonic degradation — high-stress or poorly-maintained asset."""
    rate = params.accelerated_rate * condition_mult
    noise = rng.normal(0.0, rate * 0.03)
    delta = max(0.0, rate * dt_hours + noise)
    return max(0.0, health - delta)


def degrade_abrupt(
    health: float,
    dt_hours: float,
    condition_mult: float,
    params: DegradationParams,
    rng: np.random.Generator,
) -> float:
    """Slow background drift with random sudden-step failures.

    Models components that show minimal warning before catastrophic failure.
    The sudden-step probability is per simulated hour.
    """
    # Background drift
    base_rate = params.healthy_rate * 2.0 * condition_mult
    new_health = health - base_rate * dt_hours

    # Stochastic sudden step
    step_prob = 1.0 - (1.0 - params.abrupt_failure_p) ** dt_hours
    if rng.random() < step_prob:
        step = rng.uniform(0.20, 0.60)
        new_health -= step

    return max(0.0, new_health)


def degrade_nonlinear(
    health: float,
    dt_hours: float,
    condition_mult: float,
    params: DegradationParams,
    rng: np.random.Generator,
) -> float:
    """IMS-inspired exponential acceleration below a knee point.

    Above the knee (params.nonlinear_knee) the asset is essentially healthy;
    below it the degradation rate accelerates as (1/health)^exponent, modelling
    the rapid bearing-vibration rise seen in IMS run-to-failure data.
    """
    base_rate = params.gradual_rate * condition_mult

    if health > params.nonlinear_knee:
        # Above knee: slow, nearly healthy behaviour
        rate = base_rate * 0.5
    else:
        # Below knee: exponential acceleration
        depth = params.nonlinear_knee - health  # 0 at knee, max=nonlinear_knee
        acceleration = (1.0 + depth / params.nonlinear_knee) ** params.nonlinear_exponent
        rate = base_rate * acceleration

    noise = rng.normal(0.0, rate * 0.08)
    delta = max(0.0, rate * dt_hours + noise)
    return max(0.0, health - delta)


def degrade_recoverable(
    health: float,
    dt_hours: float,
    condition_mult: float,
    params: DegradationParams,
    rng: np.random.Generator,
) -> float:
    """Gradual degradation that responds well to maintenance (same as GRADUAL).

    The recovery logic is applied separately by the maintenance model.
    This archetype is identical to GRADUAL but is tagged differently so the
    maintenance model knows to apply partial recovery instead of full replacement.
    """
    return degrade_gradual(health, dt_hours, condition_mult, params, rng)


# ─── Dispatcher ───────────────────────────────────────────────────────────────


_ARCHETYPE_FN = {
    DegradationArchetype.HEALTHY:     degrade_healthy,
    DegradationArchetype.GRADUAL:     degrade_gradual,
    DegradationArchetype.ACCELERATED: degrade_accelerated,
    DegradationArchetype.ABRUPT:      degrade_abrupt,
    DegradationArchetype.NONLINEAR:   degrade_nonlinear,
    DegradationArchetype.RECOVERABLE: degrade_recoverable,
}


def step_health(
    archetype: DegradationArchetype,
    health: float,
    dt_hours: float,
    condition_mult: float,
    params: DegradationParams,
    rng: np.random.Generator,
    degradation_multiplier: float = 1.0,
) -> float:
    """Advance health by one timestep.

    Parameters
    ----------
    archetype:
        Which degradation archetype to apply.
    health:
        Current health ∈ [0, 1].
    dt_hours:
        Timestep size in simulated hours.
    condition_mult:
        Operating-condition multiplier (from environment.py).
    params:
        DegradationParams from SimulatorConfig.
    rng:
        Component-specific Generator.
    degradation_multiplier:
        Per-asset fleet heterogeneity factor (sampled once at asset creation).

    Returns
    -------
    float
        New health value, clamped to [0.0, 1.0].
    """
    effective_mult = condition_mult * degradation_multiplier
    fn = _ARCHETYPE_FN[archetype]
    new_health = fn(health, dt_hours, effective_mult, params, rng)
    return float(np.clip(new_health, 0.0, 1.0))


def is_failed(health: float) -> bool:
    """Return True when health has dropped below the failure threshold."""
    return health <= FAILURE_HEALTH_THRESHOLD


def assign_archetype(
    rng: np.random.Generator,
    n_assets: int,
) -> DegradationArchetype:
    """Sample a degradation archetype for one component.

    Distribution inspired by real fleet behaviour:
      ~40% gradual (normal wear)
      ~20% healthy (long-life or lightly used)
      ~15% nonlinear (IMS-style bearing failure)
      ~12% accelerated (high-stress)
      ~8%  recoverable (maintenance-responsive)
      ~5%  abrupt (rare sudden failure)
    """
    weights = [0.40, 0.20, 0.15, 0.12, 0.08, 0.05]
    archetypes = [
        DegradationArchetype.GRADUAL,
        DegradationArchetype.HEALTHY,
        DegradationArchetype.NONLINEAR,
        DegradationArchetype.ACCELERATED,
        DegradationArchetype.RECOVERABLE,
        DegradationArchetype.ABRUPT,
    ]
    idx = int(rng.choice(len(archetypes), p=weights))
    return archetypes[idx]


def compute_true_rul(
    health_history: list[float],
    timestep_hours: float,
) -> list[float]:
    """Compute true RUL (hours) for a complete health trajectory.

    RUL at step t = (number of steps until failure from t) * timestep_hours.
    If the component never fails in the trajectory it is censored (RUL = None).

    Parameters
    ----------
    health_history:
        Sequence of health values from t=0 to t=T.
    timestep_hours:
        Hours per timestep.

    Returns
    -------
    list[float | None]
        True RUL at each step; None for censored trajectories.
    """
    n = len(health_history)
    # Find first failure index
    failure_idx: int | None = None
    for i, h in enumerate(health_history):
        if is_failed(h):
            failure_idx = i
            break

    rul: list[float | None] = []
    for i in range(n):
        if failure_idx is None:
            rul.append(None)  # censored
        else:
            steps_remaining = max(0, failure_idx - i)
            rul.append(float(steps_remaining * timestep_hours))
    return rul  # type: ignore[return-value]
