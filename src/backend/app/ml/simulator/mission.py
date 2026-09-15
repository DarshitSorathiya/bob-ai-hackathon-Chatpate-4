"""
Mission model for the fleet simulator.

Missions are assigned to assets based on:
  1. Asset readiness (minimum health threshold).
  2. Mission scheduling (no overlap).
  3. Fleet-level demand.

Mission records are included in observable data (they are external scheduling
decisions, not derived from health). However, mission_conflict edge cases
expose when a mission is scheduled despite the asset having insufficient RUL.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from app.ml.simulator.config import MissionParams


# ─── Mission record ────────────────────────────────────────────────────────────


@dataclass
class MissionRecord:
    """One mission assignment (observable — included in output tables)."""

    mission_id: str
    mission_code: str
    asset_id: str
    name: str
    criticality: str
    scheduled_start: datetime
    duration_hours: float
    status: str           # "PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"
    role: str             # "PRIMARY", "SUPPORT"
    is_conflict: bool     # True if RUL < duration at assignment time (edge case)


# ─── Mission scheduler ────────────────────────────────────────────────────────


@dataclass
class AssetMissionState:
    """Mission scheduling state for one asset."""

    asset_id: str
    missions: list[MissionRecord] = field(default_factory=list)
    next_mission_eligible_at: datetime | None = None

    def is_on_mission(self, ts: datetime) -> bool:
        for m in self.missions:
            end = m.scheduled_start + timedelta(hours=m.duration_hours)
            if m.scheduled_start <= ts <= end:
                return True
        return False

    def active_mission(self, ts: datetime) -> MissionRecord | None:
        for m in self.missions:
            end = m.scheduled_start + timedelta(hours=m.duration_hours)
            if m.scheduled_start <= ts <= end:
                return m
        return None


def schedule_mission(
    state: AssetMissionState,
    asset_id: str,
    asset_type: str,
    current_time: datetime,
    current_health: float,
    true_rul_hours: float | None,
    params: MissionParams,
    rng: np.random.Generator,
    force_conflict: bool = False,
) -> MissionRecord | None:
    """Attempt to schedule a new mission for an asset.

    Returns None if the asset is not eligible or health is too low.

    Parameters
    ----------
    force_conflict:
        If True, schedule a mission even if RUL < duration (edge case injection).
    """
    if current_health < params.assignment_min_health and not force_conflict:
        return None

    if not force_conflict and state.next_mission_eligible_at and current_time < state.next_mission_eligible_at:
        return None

    interval_days = rng.uniform(
        params.mission_interval_days_min,
        params.mission_interval_days_max,
    )
    start_time = current_time + timedelta(days=float(interval_days))

    duration_hours = float(rng.uniform(
        params.duration_hours_min,
        params.duration_hours_max,
    ))

    # Sample criticality
    options = list(params.criticality_weights.keys())
    weights = np.array([params.criticality_weights[c] for c in options])
    weights /= weights.sum()
    criticality = options[int(rng.choice(len(options), p=weights))]

    # Detect conflict: RUL < mission duration
    is_conflict = (
        true_rul_hours is not None and true_rul_hours < duration_hours
    ) or force_conflict

    # Deterministic IDs from RNG
    raw_id = rng.integers(0, 2**32)
    mission_code = f"MSNS-{raw_id:06X}"[:12]
    mid_bytes = rng.integers(0, 256, size=16, dtype=np.uint8).tobytes().hex()
    mission_id = f"{mid_bytes[:8]}-{mid_bytes[8:12]}-{mid_bytes[12:16]}-{mid_bytes[16:20]}-{mid_bytes[20:32]}"
    record = MissionRecord(
        mission_id=mission_id,
        mission_code=mission_code,
        asset_id=asset_id,
        name=f"Mission {mission_code} ({asset_type})",
        criticality=criticality,
        scheduled_start=start_time,
        duration_hours=duration_hours,
        status="PLANNED",
        role="PRIMARY" if rng.random() > 0.3 else "SUPPORT",
        is_conflict=is_conflict,
    )

    state.missions.append(record)
    state.next_mission_eligible_at = start_time + timedelta(
        hours=duration_hours + rng.uniform(24, 72)
    )
    return record
