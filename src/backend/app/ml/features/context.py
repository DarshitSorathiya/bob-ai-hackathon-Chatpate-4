"""
Contextual feature extractor.

Attaches context features to each telemetry row that are:
  a) Observable at prediction time (no future information)
  b) Causally valid (derived only from past events and current state)

Features produced
-----------------
Operating condition context:
  op_cond_{CONDITION}     — one-hot for each operating condition
  op_cond_is_high_stress  — 1 if condition in {TAKEOFF, COMBAT}

Component / maintenance history (all computed from past events only):
  hours_since_last_maint  — operating hours since last recorded maintenance
  maint_event_count       — total number of maintenance events up to this point
  last_maint_type_{TYPE}  — one-hot for type of most-recent maintenance event
  operating_hours         — cumulative asset operating hours (from telemetry)

Mission context (causally valid: only scheduled_start, not outcomes):
  mission_active          — 1 if current timestamp falls within a scheduled mission window
  mission_criticality_max — max criticality value of active/recent missions (0-3 scale)
  hours_until_next_mission — hours to next scheduled mission start (-1 = none scheduled)

NOTE: mission outcomes and conflict flags are NOT included — those are
labels, not features, and using them at prediction time would be leakage.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Operating condition order / encoding
OPERATING_CONDITIONS: list[str] = [
    "IDLE", "CRUISE", "TAKEOFF", "COMBAT", "MAINTENANCE_GROUND",
]
HIGH_STRESS_CONDITIONS: frozenset[str] = frozenset({"TAKEOFF", "COMBAT"})

CRITICALITY_MAP: dict[str, int] = {
    "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4,
}


def compute_context_features(
    telemetry_clean: pd.DataFrame,
    maintenance_df: pd.DataFrame,
    missions_df: pd.DataFrame,
) -> pd.DataFrame:
    """Attach context features to cleaned telemetry.

    Parameters
    ----------
    telemetry_clean:
        Cleaned telemetry sorted by (asset_id, sensor_id, recorded_at).
        Required columns: asset_id, sensor_id, component_id, recorded_at,
        operating_condition, operating_hours.
    maintenance_df:
        Observable maintenance events table.
        Required columns: asset_id, component_id, performed_at,
        asset_hours_at_event, event_type.
    missions_df:
        Observable missions table.
        Required columns: asset_id, scheduled_start, duration_hours,
        criticality, status.

    Returns
    -------
    pd.DataFrame
        telemetry_clean with context feature columns appended.
    """
    if telemetry_clean.empty:
        return telemetry_clean.copy()

    df = telemetry_clean.copy()
    df["recorded_at"] = pd.to_datetime(df["recorded_at"], utc=True)

    # --- Operating condition one-hots ---
    for cond in OPERATING_CONDITIONS:
        df[f"op_cond_{cond}"] = (df["operating_condition"] == cond).astype(int)
    df["op_cond_is_high_stress"] = df["operating_condition"].isin(HIGH_STRESS_CONDITIONS).astype(int)

    # --- Maintenance context (per asset × component × timestamp) ---
    df = _attach_maintenance_context(df, maintenance_df)

    # --- Mission context (per asset × timestamp) ---
    df = _attach_mission_context(df, missions_df)

    return df


# ─── Maintenance context ──────────────────────────────────────────────────────


def _attach_maintenance_context(
    df: pd.DataFrame,
    maintenance_df: pd.DataFrame,
) -> pd.DataFrame:
    """Attach maintenance recency features per (asset_id, component_id)."""
    # Default values
    df["hours_since_last_maint"] = np.nan
    df["maint_event_count"] = 0
    for mtype in ["SCHEDULED", "CORRECTIVE", "REPLACEMENT"]:
        df[f"last_maint_type_{mtype}"] = 0

    if maintenance_df.empty:
        return df

    maint = maintenance_df.copy()
    maint["performed_at"] = pd.to_datetime(maint["performed_at"], utc=True)
    maint_sorted = maint.sort_values("performed_at")

    for (asset_id, comp_id), group in df.groupby(["asset_id", "component_id"], sort=False):
        comp_maint = maint_sorted[
            (maint_sorted["asset_id"] == asset_id) &
            (maint_sorted["component_id"] == comp_id)
        ]
        if comp_maint.empty:
            # No maintenance at all — set hours_since_last_maint to operating_hours
            df.loc[group.index, "hours_since_last_maint"] = group["operating_hours"].values
            continue

        maint_times = comp_maint["performed_at"].values
        maint_hours = comp_maint["asset_hours_at_event"].values
        maint_types = comp_maint["event_type"].values

        for idx_label, row in group.iterrows():
            ts = row["recorded_at"]
            oh = row["operating_hours"]
            # Past maintenance only (strictly before current timestamp)
            # Convert to int64 nanoseconds for tz-safe comparison
            ts_ns = np.int64(ts.value)
            maint_ns = maint_times.astype("datetime64[ns]").view("int64")
            past_mask = maint_ns < ts_ns
            past_count = int(past_mask.sum())

            df.at[idx_label, "maint_event_count"] = past_count

            if past_count == 0:
                df.at[idx_label, "hours_since_last_maint"] = oh
            else:
                last_oh = float(maint_hours[past_mask][-1])
                df.at[idx_label, "hours_since_last_maint"] = max(0.0, oh - last_oh)
                last_type = str(maint_types[past_mask][-1])
                for mtype in ["SCHEDULED", "CORRECTIVE", "REPLACEMENT"]:
                    df.at[idx_label, f"last_maint_type_{mtype}"] = int(last_type == mtype)

    return df


# ─── Mission context ──────────────────────────────────────────────────────────


def _attach_mission_context(
    df: pd.DataFrame,
    missions_df: pd.DataFrame,
) -> pd.DataFrame:
    """Attach mission-aware context features per (asset_id, timestamp)."""
    df["mission_active"] = 0
    df["mission_criticality_max"] = 0
    df["hours_until_next_mission"] = -1.0

    if missions_df.empty:
        return df

    missions = missions_df.copy()
    missions["scheduled_start"] = pd.to_datetime(missions["scheduled_start"], utc=True)
    # Compute end time from start + duration
    missions["scheduled_end"] = missions["scheduled_start"] + pd.to_timedelta(
        missions["duration_hours"], unit="h"
    )
    missions["criticality_int"] = missions["criticality"].map(CRITICALITY_MAP).fillna(1)

    for asset_id, asset_group in df.groupby("asset_id", sort=False):
        asset_missions = missions[missions["asset_id"] == asset_id].copy()
        if asset_missions.empty:
            continue

        for idx_label, row in asset_group.iterrows():
            ts = row["recorded_at"]

            # Active mission: current timestamp falls within [start, end)
            active = asset_missions[
                (asset_missions["scheduled_start"] <= ts) &
                (asset_missions["scheduled_end"] > ts)
            ]
            df.at[idx_label, "mission_active"] = int(len(active) > 0)
            if len(active) > 0:
                df.at[idx_label, "mission_criticality_max"] = int(
                    active["criticality_int"].max()
                )

            # Hours until next mission (future missions — valid to use scheduled time)
            future = asset_missions[asset_missions["scheduled_start"] > ts]
            if len(future) > 0:
                next_start = future["scheduled_start"].min()
                delta_hours = (next_start - ts).total_seconds() / 3600.0
                df.at[idx_label, "hours_until_next_mission"] = round(delta_hours, 1)

    return df
