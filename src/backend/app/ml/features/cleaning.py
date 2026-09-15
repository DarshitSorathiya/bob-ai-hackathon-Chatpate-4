"""
Telemetry cleaning — normalise raw observable telemetry before feature extraction.

Operations (all applied in order)
----------------------------------
1. Parse recorded_at to datetime with UTC timezone
2. De-duplicate exact (sensor_id, recorded_at) pairs (keep first)
3. Sort by (asset_id, sensor_id, recorded_at)
4. Clip values to [critical_min, critical_max] using sensor metadata
5. Attach a ``is_clean`` boolean flag (False = clipped or was a duplicate)

CRITICAL: no imputation of missing timestamps is performed here.
Feature extractors handle missingness explicitly by computing missingness
indicators and using configurable fill strategies.
"""

from __future__ import annotations

import pandas as pd


def clean_telemetry(
    telemetry_df: pd.DataFrame,
    sensors_df: pd.DataFrame,
    *,
    clip_to_critical_bounds: bool = True,
) -> pd.DataFrame:
    """Clean raw telemetry.

    Parameters
    ----------
    telemetry_df:
        Raw telemetry from the simulator (or DB).
        Required columns: asset_id, sensor_id, value, recorded_at.
    sensors_df:
        Sensor metadata (from simulator or DB).
        Required columns: sensor_id, critical_min, critical_max.
    clip_to_critical_bounds:
        If True, values outside [critical_min, critical_max] are clipped
        and flagged with ``is_clean=False``.

    Returns
    -------
    pd.DataFrame
        Cleaned telemetry with additional column ``is_clean``.
    """
    if telemetry_df.empty:
        out = telemetry_df.copy()
        out["is_clean"] = True
        return out

    df = telemetry_df.copy()

    # 1. Parse timestamps
    df["recorded_at"] = pd.to_datetime(df["recorded_at"], utc=True)

    # 2. Mark duplicates (keep first occurrence)
    dup_mask = df.duplicated(subset=["sensor_id", "recorded_at"], keep="first")
    df["is_clean"] = ~dup_mask
    df = df[~dup_mask].copy()

    # 3. Sort
    df = df.sort_values(["asset_id", "sensor_id", "recorded_at"]).reset_index(drop=True)

    # 4. Clip to critical bounds
    if clip_to_critical_bounds and not sensors_df.empty:
        bounds = sensors_df.set_index("sensor_id")[["critical_min", "critical_max"]]
        merged = df.merge(bounds, left_on="sensor_id", right_index=True, how="left")
        has_bounds = merged["critical_min"].notna() & merged["critical_max"].notna()

        # Detect out-of-range before clipping
        out_of_range = has_bounds & (
            (merged["value"] < merged["critical_min"]) |
            (merged["value"] > merged["critical_max"])
        )
        df.loc[out_of_range.values, "is_clean"] = False

        # Clip
        df["value"] = merged["value"].clip(
            lower=merged["critical_min"],
            upper=merged["critical_max"],
        ).values

    return df
