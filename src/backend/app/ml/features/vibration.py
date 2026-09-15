"""
Vibration-specific feature extractor.

Computes time-domain and proxy frequency-domain features from vibration
sensor readings. All features are computed from rolling windows of
observed values — no raw waveform is available from the simulator
(which emits 1-Hz scalar RMS/bearing values). This module extracts the
features that are derivable from that scalar stream.

Time-domain features (per rolling window)
------------------------------------------
  rms            — root mean square of the window (≡ sqrt(mean(x²)))
  kurtosis       — statistical kurtosis of the window (healthy ≈ 3; fault >> 3)
  crest_factor   — peak / rms (always ≥ 1; high → impulsive faults)
  peak           — max absolute value in window
  peak_to_peak   — max − min in window

Spectral proxy (no raw waveform — computed from inter-step differences)
------------------------------------------------------------------------
  delta_rms      — absolute difference between consecutive readings
  delta_rms_mean — rolling mean of delta_rms (approximates spectral energy)
  delta_rms_std  — rolling std of delta_rms

These are labelled VIBRATION_* for VIBRATION_RMS sensor type and
BEARING_VIBRATION_* for BEARING_VIBRATION sensor type.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from app.ml.features.rolling import DEFAULT_WINDOWS, _safe_col

# Sensor types that are treated as vibration sources
VIBRATION_SENSOR_TYPES: frozenset[str] = frozenset({
    "VIBRATION_RMS",
    "BEARING_VIBRATION",
})


def compute_vibration_features(
    telemetry_clean: pd.DataFrame,
    sensors_df: pd.DataFrame,
    windows: Sequence[int] = DEFAULT_WINDOWS,
) -> pd.DataFrame:
    """Compute vibration-specific features for vibration-type sensors.

    Non-vibration sensors are passed through unchanged.

    Parameters
    ----------
    telemetry_clean:
        Cleaned, sorted telemetry. Required columns: asset_id, sensor_id, value.
    sensors_df:
        Sensor metadata. Required columns: sensor_id, sensor_type.
    windows:
        Rolling window sizes.

    Returns
    -------
    pd.DataFrame
        Original telemetry with vibration feature columns appended.
        Non-vibration rows have NaN in vibration columns.
    """
    if telemetry_clean.empty:
        return telemetry_clean.copy()

    if sensors_df.empty or "sensor_type" not in sensors_df.columns:
        return telemetry_clean.copy()

    stype_map: dict[str, str] = sensors_df.set_index("sensor_id")["sensor_type"].to_dict()

    # Identify vibration sensor IDs in this dataset
    vib_sensor_ids: set[str] = {
        sid for sid, stype in stype_map.items()
        if stype in VIBRATION_SENSOR_TYPES
    }

    if not vib_sensor_ids:
        return telemetry_clean.copy()

    result_parts: list[pd.DataFrame] = []

    for (asset_id, sensor_id), group in telemetry_clean.groupby(
        ["asset_id", "sensor_id"], sort=False
    ):
        if sensor_id not in vib_sensor_ids:
            result_parts.append(pd.DataFrame(index=group.index))
            continue

        stype = stype_map.get(sensor_id, "VIBRATION")
        prefix = _safe_col(stype)
        gidx = group.index
        values = group["value"].values.astype(float)
        n = len(values)

        chunk: dict[str, np.ndarray] = {}

        for w in windows:
            rms_arr = np.zeros(n)
            kurt_arr = np.zeros(n)
            crest_arr = np.ones(n)
            peak_arr = np.zeros(n)
            ptp_arr = np.zeros(n)

            for i in range(n):
                start = max(0, i - w + 1)
                seg = values[start : i + 1]
                rms = float(np.sqrt(np.mean(seg ** 2)))
                peak = float(np.max(np.abs(seg)))
                rms_arr[i] = rms
                kurt_arr[i] = float(_kurtosis(seg))
                crest_arr[i] = peak / rms if rms > 1e-10 else 1.0
                peak_arr[i] = float(np.max(seg))
                ptp_arr[i] = float(np.max(seg) - np.min(seg))

            chunk[f"{prefix}_vib_roll{w}_rms"] = rms_arr
            chunk[f"{prefix}_vib_roll{w}_kurtosis"] = kurt_arr
            chunk[f"{prefix}_vib_roll{w}_crest_factor"] = crest_arr
            chunk[f"{prefix}_vib_roll{w}_peak"] = peak_arr
            chunk[f"{prefix}_vib_roll{w}_peak_to_peak"] = ptp_arr

        # Delta features (no window needed — just consecutive diffs)
        delta = np.zeros(n)
        delta[1:] = np.abs(np.diff(values))
        chunk[f"{prefix}_delta_rms"] = delta

        # Rolling stats on delta
        delta_series = pd.Series(delta)
        for w in windows:
            rolled = delta_series.rolling(window=w, min_periods=1)
            chunk[f"{prefix}_delta_roll{w}_mean"] = rolled.mean().values
            chunk[f"{prefix}_delta_roll{w}_std"] = rolled.std(ddof=1).fillna(0.0).values

        result_parts.append(pd.DataFrame(chunk, index=gidx))

    if not result_parts:
        return telemetry_clean.copy()

    features = pd.concat(result_parts, axis=0)
    return pd.concat([telemetry_clean, features.reindex(telemetry_clean.index)], axis=1)


def _kurtosis(arr: np.ndarray) -> float:
    """Fisher kurtosis (excess; normal = 0)."""
    n = len(arr)
    if n < 4:
        return 0.0
    mean = arr.mean()
    std = arr.std()
    if std < 1e-12:
        return 0.0
    return float(np.mean(((arr - mean) / std) ** 4) - 3.0)
