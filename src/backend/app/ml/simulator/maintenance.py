"""
Maintenance model for the fleet simulator.

Maintenance events:
  1. Scheduled preventive — triggered when component reaches a fraction of MTBF.
  2. Corrective — triggered when health falls below corrective_trigger_health.
  3. Component replacement — with probability replacement_probability per event.

Maintenance effects on health:
  - Non-replacement (repair/overhaul): health restored to recovery_health_gain * 1.0.
  - Component replacement: health set to component_replacement_health (near new).
  - Recovery curve: health improves smoothly over recovery_timesteps after maintenance.

Asset status during maintenance:
  - Operating condition forced to MAINTENANCE_GROUND.
  - Telemetry is still emitted (with MAINTENANCE_GROUND baseline).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from app.ml.simulator.config import MaintenanceParams


# ─── Maintenance event record ─────────────────────────────────────────────────


@dataclass
class MaintenanceEvent:
    """One maintenance event (observable — included in output tables)."""

    event_id: str
    asset_id: str
    component_id: str
    event_type: str        # "SCHEDULED", "CORRECTIVE", "REPLACEMENT"
    performed_at: datetime
    asset_hours_at_event: float
    description: str
    # Note: health values are NOT stored here (they live in TruthLayer only).


# ─── Maintenance state (mutable, per component) ──────────────────────────────


@dataclass
class ComponentMaintenanceState:
    """Mutable maintenance state for one component."""

    component_id: str
    asset_id: str
    mtbf_hours: float               # component-specific MTBF (with heterogeneity)

    hours_since_last_maintenance: float = 0.0
    maintenance_active: bool = False
    maintenance_steps_remaining: int = 0
    recovery_steps_remaining: int = 0
    post_maintenance_health_target: float = 0.9

    events: list[MaintenanceEvent] = field(default_factory=list)

    def is_overdue(self, params: MaintenanceParams) -> bool:
        """Return True if maintenance is past the scheduled threshold."""
        return (
            self.hours_since_last_maintenance
            > self.mtbf_hours * params.scheduled_fraction * 1.20  # 20% overdue window
        )

    def schedule_due(self, params: MaintenanceParams) -> bool:
        """Return True if scheduled maintenance is now due."""
        return (
            self.hours_since_last_maintenance
            >= self.mtbf_hours * params.scheduled_fraction
        )


# ─── Maintenance decision logic ────────────────────────────────────────────────


def should_trigger_maintenance(
    state: ComponentMaintenanceState,
    health: float,
    params: MaintenanceParams,
) -> bool:
    """Return True when a maintenance event should be initiated."""
    if state.maintenance_active:
        return False
    if state.schedule_due(params):
        return True
    if health <= params.corrective_trigger_health:
        return True
    return False


def start_maintenance(
    state: ComponentMaintenanceState,
    asset_id: str,
    component_id: str,
    current_time: datetime,
    asset_hours: float,
    health: float,
    params: MaintenanceParams,
    rng: np.random.Generator,
) -> tuple[MaintenanceEvent, float]:
    """Begin a maintenance event and return the target post-maintenance health.

    Returns
    -------
    (event, target_health)
    """
    is_corrective = health <= params.corrective_trigger_health
    is_replacement = rng.random() < params.replacement_probability

    if is_replacement:
        event_type = "REPLACEMENT"
        target_health = params.component_replacement_health
    elif is_corrective:
        event_type = "CORRECTIVE"
        target_health = params.recovery_health_gain
    else:
        event_type = "SCHEDULED"
        target_health = params.recovery_health_gain

    duration_hours = rng.uniform(params.duration_hours_min, params.duration_hours_max)
    # Duration → steps (round up)
    duration_steps = max(1, int(duration_hours))

    # Deterministic event_id from component_id + timestamp
    event_key = f"{component_id}:{current_time.isoformat()}"
    event_id = hashlib.sha256(event_key.encode()).hexdigest()[:32]
    event_id = f"{event_id[:8]}-{event_id[8:12]}-{event_id[12:16]}-{event_id[16:20]}-{event_id[20:32]}"

    event = MaintenanceEvent(
        event_id=event_id,
        asset_id=asset_id,
        component_id=component_id,
        event_type=event_type,
        performed_at=current_time,
        asset_hours_at_event=asset_hours,
        description=f"{event_type} maintenance for component {component_id}",
    )

    state.maintenance_active = True
    state.maintenance_steps_remaining = duration_steps
    state.post_maintenance_health_target = target_health
    state.recovery_steps_remaining = params.recovery_timesteps
    state.events.append(event)

    return event, target_health


def step_maintenance(
    state: ComponentMaintenanceState,
    current_health: float,
    dt_hours: float,
) -> tuple[float, bool]:
    """Advance maintenance state by one timestep.

    Returns
    -------
    (new_health, maintenance_completed_this_step)
        maintenance_completed_this_step is True in the step when maintenance ends.
    """
    completed = False

    if state.maintenance_active:
        state.maintenance_steps_remaining -= 1
        if state.maintenance_steps_remaining <= 0:
            state.maintenance_active = False
            state.hours_since_last_maintenance = 0.0
            completed = True
            return state.post_maintenance_health_target, completed

        # During maintenance: health improves gradually toward target
        progress = 1.0 - state.maintenance_steps_remaining / max(
            1, state.maintenance_steps_remaining + 1
        )
        recovery_gain = (
            (state.post_maintenance_health_target - current_health) * progress * 0.3
        )
        return min(state.post_maintenance_health_target, current_health + recovery_gain), completed

    # Recovery phase after maintenance
    if state.recovery_steps_remaining > 0:
        state.recovery_steps_remaining -= 1
        # Smooth approach to target using exponential ease
        gap = state.post_maintenance_health_target - current_health
        recovery = gap * 0.15
        return min(state.post_maintenance_health_target, current_health + recovery), completed

    # Normal operation
    state.hours_since_last_maintenance += dt_hours
    return current_health, completed
