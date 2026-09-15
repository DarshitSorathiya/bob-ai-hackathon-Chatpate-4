"""
Label generator — creates ML training targets from simulator truth.

CRITICAL DESIGN RULE
---------------------
Labels are joined to features using the (component_id, recorded_at) key.
The join is LEFT from features → truth so that:
  - Every feature row gets its label from the truth AT THAT TIMESTAMP
  - No future health, failure timestamps, or future RUL values are used
    as feature inputs
  - The truth tables are NEVER included in the feature DataFrame itself

Labels produced
---------------
rul_cycles        — true remaining useful life in timestep-hours at each step
                    (from truth trajectory; capped at rul_cap to match C-MAPSS
                    piecewise-linear convention)
failure_within_24h — 1 if component fails within the next 24 hours
failure_within_72h — 1 if component fails within the next 72 hours
failure_within_mission_window — 1 if component fails within next N hours
                    (N = mission_horizon_hours parameter)
health_class      — categorical: HEALTHY (>0.7), DEGRADED (0.3-0.7),
                    CRITICAL (<0.3)

Anti-leakage guarantee
-----------------------
The LabelGenerator.generate() method returns a SEPARATE labels DataFrame,
not a DataFrame with labels appended to features. The caller must keep
them separate and only join them at the model training layer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# Health class thresholds (applied to true_health from truth)
HEALTH_THRESHOLD_HEALTHY: float = 0.70
HEALTH_THRESHOLD_CRITICAL: float = 0.30


@dataclass
class LabelSet:
    """Container for ML training labels, kept strictly separate from features."""

    component_id: str
    asset_id: str
    # Index aligns with the feature DataFrame rows for this component
    timestamps: list[str]
    rul_cycles: list[float]          # capped RUL in timestep units
    failure_within_24h: list[int]    # binary
    failure_within_72h: list[int]    # binary
    failure_within_window: list[int] # binary (configurable window)
    health_class: list[str]          # HEALTHY / DEGRADED / CRITICAL

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame({
            "component_id": self.component_id,
            "asset_id": self.asset_id,
            "timestamp": self.timestamps,
            "rul_cycles": self.rul_cycles,
            "failure_within_24h": self.failure_within_24h,
            "failure_within_72h": self.failure_within_72h,
            "failure_within_window": self.failure_within_window,
            "health_class": self.health_class,
        })


class LabelGenerator:
    """Generate training labels from simulator truth tables.

    Parameters
    ----------
    timestep_hours:
        Hours between simulator timesteps (default 1.0).
    rul_cap:
        Maximum RUL in hours to clip to (matches piecewise-linear convention).
        Default 125 * 24 = 3000 h.
    mission_horizon_hours:
        Window for failure_within_mission_window label.
    """

    def __init__(
        self,
        timestep_hours: float = 1.0,
        rul_cap: float = 3000.0,
        mission_horizon_hours: float = 72.0,
    ) -> None:
        self.timestep_hours = timestep_hours
        self.rul_cap = rul_cap
        self.mission_horizon_hours = mission_horizon_hours

    def generate(
        self,
        health_trajectories: pd.DataFrame,
        failure_events: pd.DataFrame,
    ) -> pd.DataFrame:
        """Generate labels for all components in the truth tables.

        Parameters
        ----------
        health_trajectories:
            truth['component_health_trajectories'] from SimulationResult.
            Required columns: component_id, asset_id, step, timestamp,
            true_health, true_rul.
        failure_events:
            truth['failure_events'] from SimulationResult.
            Required columns: component_id, asset_id, occurred_at.

        Returns
        -------
        pd.DataFrame
            Labels DataFrame with columns:
              component_id, asset_id, timestamp,
              rul_cycles, failure_within_24h, failure_within_72h,
              failure_within_window, health_class
            IMPORTANT: do NOT merge this into the features DataFrame
            before training — pass separately to the model.
        """
        if health_trajectories.empty:
            return pd.DataFrame(columns=[
                "component_id", "asset_id", "timestamp",
                "rul_cycles", "failure_within_24h", "failure_within_72h",
                "failure_within_window", "health_class",
            ])

        # Build failure time lookup: component_id → failure_timestamp
        failure_lookup: dict[str, pd.Timestamp] = {}
        if not failure_events.empty:
            for _, row in failure_events.iterrows():
                cid = row["component_id"]
                ft = pd.Timestamp(row["occurred_at"])
                if not hasattr(ft, "tzinfo") or ft.tzinfo is None:
                    ft = ft.tz_localize("UTC")
                failure_lookup[cid] = ft

        label_parts: list[pd.DataFrame] = []
        for (comp_id, asset_id), traj in health_trajectories.groupby(
            ["component_id", "asset_id"], sort=False
        ):
            traj = traj.sort_values("step").copy()
            traj["timestamp"] = pd.to_datetime(traj["timestamp"], utc=True)

            n = len(traj)
            true_health = traj["true_health"].values.astype(float)
            true_rul_raw = traj["true_rul"].fillna(0.0).values.astype(float)
            timestamps = traj["timestamp"].values  # numpy datetime64

            # RUL: cap at rul_cap and ensure non-negative
            rul = np.clip(true_rul_raw * self.timestep_hours, 0.0, self.rul_cap)

            # Failure binary labels
            failure_ts = failure_lookup.get(str(comp_id))
            fw24 = np.zeros(n, dtype=int)
            fw72 = np.zeros(n, dtype=int)
            fw_window = np.zeros(n, dtype=int)

            if failure_ts is not None:
                # Use int64 nanosecond comparison to avoid tz-repr warnings
                failure_ns = np.int64(failure_ts.value)
                timestamps_ns = timestamps.astype("datetime64[ns]").view("int64")
                for i in range(n):
                    delta_h = float(failure_ns - timestamps_ns[i]) / 3_600_000_000_000.0
                    if 0.0 <= delta_h <= 24.0:
                        fw24[i] = 1
                    if 0.0 <= delta_h <= 72.0:
                        fw72[i] = 1
                    if 0.0 <= delta_h <= self.mission_horizon_hours:
                        fw_window[i] = 1

            # Health class
            health_class = np.where(
                true_health >= HEALTH_THRESHOLD_HEALTHY, "HEALTHY",
                np.where(true_health >= HEALTH_THRESHOLD_CRITICAL, "DEGRADED", "CRITICAL"),
            )

            label_df = pd.DataFrame({
                "component_id": str(comp_id),
                "asset_id": str(asset_id),
                "timestamp": traj["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00").values,
                "rul_cycles": rul,
                "failure_within_24h": fw24,
                "failure_within_72h": fw72,
                "failure_within_window": fw_window,
                "health_class": health_class,
            })
            label_parts.append(label_df)

        return pd.concat(label_parts, ignore_index=True)

    def label_summary(self, labels_df: pd.DataFrame) -> dict[str, object]:
        """Return summary statistics for a labels DataFrame."""
        if labels_df.empty:
            return {"n_rows": 0}
        return {
            "n_rows": len(labels_df),
            "n_components": labels_df["component_id"].nunique(),
            "rul_min": float(labels_df["rul_cycles"].min()),
            "rul_max": float(labels_df["rul_cycles"].max()),
            "rul_mean": float(labels_df["rul_cycles"].mean()),
            "failure_within_24h_rate": float(labels_df["failure_within_24h"].mean()),
            "failure_within_72h_rate": float(labels_df["failure_within_72h"].mean()),
            "failure_within_window_rate": float(labels_df["failure_within_window"].mean()),
            "health_class_dist": labels_df["health_class"].value_counts().to_dict(),
        }

    def validate_no_leakage(self, features_df: pd.DataFrame) -> list[str]:
        """Check that features_df contains no label columns (leakage guard)."""
        forbidden = {
            "rul_cycles", "true_rul", "true_health", "failure_within_24h",
            "failure_within_72h", "failure_within_window", "health_class",
            "failure_label", "failure_event", "failure_timestamp",
        }
        found = forbidden.intersection(features_df.columns)
        return sorted(found)
