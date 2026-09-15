"""
Rolling statistics feature extractor.

Computes rolling window features per (asset_id, sensor_id) stream.
All features are computed using ONLY past observations — no future values
are used at any point (``min_periods=1`` is used to avoid NaN flood at
the start of each series but features computed with <window observations
are annotated with the insufficient_history quality flag elsewhere).

Features produced
-----------------
For each sensor_id × window_size combination:
  {sensor_type}_roll{w}_mean       — rolling mean
  {sensor_type}_roll{w}_std        — rolling std (ddof=1; 0 for single obs)
  {sensor_type}_roll{w}_min        — rolling min
  {sensor_type}_roll{w}_max        — rolling max
  {sensor_type}_roll{w}_range      — rolling max − min
  {sensor_type}_roll{w}_slope      — OLS slope of value vs step index (trend)
  {sensor_type}_roll{w}_roc        — rate-of-change = (last − first) / w
  {sensor_type}_ewm{a}_mean        — exponentially-weighted mean (alpha = a)

Column naming uses the sensor_type (e.g. VIBRATION_RMS) not the sensor_id
UUID so that features are consistent across assets/components.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


# ─── Default windows ──────────────────────────────────────────────────────────

DEFAULT_WINDOWS: list[int] = [6, 24, 72]   # hours (assuming 1 h timestep)
DEFAULT_EWM_ALPHAS: list[float] = [0.1, 0.3]


# ─── Public API ───────────────────────────────────────────────────────────────


def compute_rolling_features(
    telemetry_clean: pd.DataFrame,
    sensors_df: pd.DataFrame,
    windows: Sequence[int] = DEFAULT_WINDOWS,
    ewm_alphas: Sequence[float] = DEFAULT_EWM_ALPHAS,
) -> pd.DataFrame:
    """Compute rolling statistics for each (asset_id, sensor_id) stream.

    Parameters
    ----------
    telemetry_clean:
        Cleaned telemetry (output of cleaning.clean_telemetry).
        Required columns: asset_id, sensor_id, component_id, value, recorded_at.
        Must be sorted by (asset_id, sensor_id, recorded_at).
    sensors_df:
        Sensor metadata; used to map sensor_id → sensor_type for column naming.
        Required columns: sensor_id, sensor_type.
    windows:
        List of rolling window sizes (in timesteps, i.e. hours at 1 h timestep).
    ewm_alphas:
        EWM smoothing factors.

    Returns
    -------
    pd.DataFrame
        One row per original telemetry row, with rolling feature columns appended.
        Index matches telemetry_clean.
    """
    if telemetry_clean.empty:
        return telemetry_clean.copy()

    # Build sensor_id → sensor_type lookup
    if not sensors_df.empty and "sensor_type" in sensors_df.columns:
        stype_map: dict[str, str] = sensors_df.set_index("sensor_id")["sensor_type"].to_dict()
    else:
        stype_map = {}

    result_parts: list[pd.DataFrame] = []

    for (asset_id, sensor_id), group in telemetry_clean.groupby(
        ["asset_id", "sensor_id"], sort=False
    ):
        stype = stype_map.get(sensor_id, sensor_id[:8])
        prefix = _safe_col(stype)
        gidx = group.index
        values = group["value"]
        n = len(values)

        chunk: dict[str, np.ndarray] = {}

        # Rolling windows
        for w in windows:
            rolled = values.rolling(window=w, min_periods=1)
            chunk[f"{prefix}_roll{w}_mean"] = rolled.mean().values
            chunk[f"{prefix}_roll{w}_std"] = rolled.std(ddof=1).fillna(0.0).values
            chunk[f"{prefix}_roll{w}_min"] = rolled.min().values
            chunk[f"{prefix}_roll{w}_max"] = rolled.max().values
            chunk[f"{prefix}_roll{w}_range"] = (
                rolled.max().values - rolled.min().values
            )
            chunk[f"{prefix}_roll{w}_slope"] = _rolling_slope(values.values, w)
            chunk[f"{prefix}_roll{w}_roc"] = _rolling_roc(values.values, w)

        # EWM
        for alpha in ewm_alphas:
            alpha_str = str(alpha).replace(".", "")
            chunk[f"{prefix}_ewm{alpha_str}_mean"] = (
                values.ewm(alpha=alpha, min_periods=1, adjust=False).mean().values
            )

        feat_df = pd.DataFrame(chunk, index=gidx)
        result_parts.append(feat_df)

    if not result_parts:
        return telemetry_clean.copy()

    features = pd.concat(result_parts, axis=0)

    # Reindex to preserve original row order and fill missing sensor columns with NaN
    return pd.concat([telemetry_clean, features.reindex(telemetry_clean.index)], axis=1)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _safe_col(name: str) -> str:
    """Convert sensor type to a safe column name prefix."""
    return name.upper().replace(" ", "_").replace("-", "_")


def _rolling_slope(values: np.ndarray, window: int) -> np.ndarray:
    """OLS slope of value vs step index over rolling window (causal)."""
    n = len(values)
    out = np.zeros(n, dtype=float)
    for i in range(n):
        start = max(0, i - window + 1)
        seg = values[start : i + 1]
        k = len(seg)
        if k < 2:
            out[i] = 0.0
            continue
        x = np.arange(k, dtype=float)
        # OLS slope: cov(x,y) / var(x)
        x_mean = x.mean()
        y_mean = seg.mean()
        denom = ((x - x_mean) ** 2).sum()
        if denom < 1e-12:
            out[i] = 0.0
        else:
            out[i] = float(((x - x_mean) * (seg - y_mean)).sum() / denom)
    return out


def _rolling_roc(values: np.ndarray, window: int) -> np.ndarray:
    """Rate of change = (current - value[i-window]) / window (causal)."""
    n = len(values)
    out = np.zeros(n, dtype=float)
    for i in range(1, n):
        start = max(0, i - window)
        out[i] = (values[i] - values[start]) / max(1, i - start)
    return out
