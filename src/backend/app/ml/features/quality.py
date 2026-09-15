"""
Data quality detection for raw telemetry streams.

Detects 8 quality failure modes and attaches a per-row reason code.
All detection is performed on OBSERVABLE data only — no truth columns used.

Reason codes (QualityFlag enum values)
---------------------------------------
MISSING             — expected reading absent
STALE               — value unchanged for N consecutive steps
STUCK               — value constant at extreme within nominal band
OUTLIER             — value > k·sigma from rolling mean (IQR method)
DRIFT               — monotonic trend exceeding drift_threshold over window
DUPLICATE           — identical (sensor_id, recorded_at) pair
INVALID_RANGE       — value outside sensor's critical_min / critical_max
INSUFFICIENT_HISTORY — fewer than min_history_steps readings for this asset·sensor
OK                  — no quality issue detected

Usage
-----
detector = DataQualityDetector(sensors_df)
flags_df = detector.flag(telemetry_df)
# flags_df has all original columns + quality_flag + quality_reason
"""

from __future__ import annotations

from enum import Enum

import numpy as np
import pandas as pd


# ─── Quality flag definitions ─────────────────────────────────────────────────


class QualityFlag(str, Enum):
    OK = "OK"
    MISSING = "MISSING"
    STALE = "STALE"
    STUCK = "STUCK"
    OUTLIER = "OUTLIER"
    DRIFT = "DRIFT"
    DUPLICATE = "DUPLICATE"
    INVALID_RANGE = "INVALID_RANGE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


# Priority ordering for multi-flag resolution (higher index = higher priority)
_FLAG_PRIORITY: dict[QualityFlag, int] = {
    QualityFlag.OK: 0,
    QualityFlag.INSUFFICIENT_HISTORY: 1,
    QualityFlag.MISSING: 2,
    QualityFlag.STALE: 3,
    QualityFlag.STUCK: 4,
    QualityFlag.DRIFT: 5,
    QualityFlag.OUTLIER: 6,
    QualityFlag.DUPLICATE: 7,
    QualityFlag.INVALID_RANGE: 8,
}


class DataQualityDetector:
    """Detects data quality issues in a telemetry DataFrame.

    Parameters
    ----------
    sensors_df:
        The ``sensors`` observable table from the simulator (or DB).
        Required columns: sensor_id, sensor_type, critical_min, critical_max,
        nominal_min, nominal_max.
    stale_window:
        Number of consecutive identical readings to trigger STALE flag.
    stuck_window:
        Number of readings to use when checking STUCK condition.
    outlier_iqr_multiplier:
        IQR multiplier for outlier detection (default 3.0 — conservative).
    drift_window:
        Rolling window size for drift trend detection.
    drift_threshold:
        Fraction of (nominal_max - nominal_min) per drift_window steps that
        constitutes a drift violation.
    min_history_steps:
        Minimum reading count required before rolling features are reliable.
    """

    def __init__(
        self,
        sensors_df: pd.DataFrame,
        stale_window: int = 10,
        stuck_window: int = 30,
        outlier_iqr_multiplier: float = 3.0,
        drift_window: int = 24,
        drift_threshold: float = 0.30,
        min_history_steps: int = 10,
    ) -> None:
        self._sensor_meta = (
            sensors_df.set_index("sensor_id")[
                ["sensor_type", "critical_min", "critical_max", "nominal_min", "nominal_max"]
            ].copy()
            if not sensors_df.empty
            else pd.DataFrame(
                columns=["sensor_type", "critical_min", "critical_max",
                         "nominal_min", "nominal_max"]
            )
        )
        self.stale_window = stale_window
        self.stuck_window = stuck_window
        self.outlier_iqr_multiplier = outlier_iqr_multiplier
        self.drift_window = drift_window
        self.drift_threshold = drift_threshold
        self.min_history_steps = min_history_steps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def flag(self, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        """Assign quality flags to every row in *telemetry_df*.

        Returns a copy with two additional columns:
          - ``quality_flag``   (QualityFlag string value)
          - ``quality_reason`` (human-readable description)

        The input DataFrame must have columns:
          asset_id, sensor_id, value, recorded_at
        """
        if telemetry_df.empty:
            out = telemetry_df.copy()
            out["quality_flag"] = QualityFlag.OK.value
            out["quality_reason"] = ""
            return out

        tel = telemetry_df.copy()
        tel["recorded_at_dt"] = pd.to_datetime(tel["recorded_at"], utc=True)

        # Initialise flags
        tel["quality_flag"] = QualityFlag.OK.value
        tel["quality_reason"] = ""

        # Run each rule; each modifies flags in-place on the grouped copy
        tel = self._flag_duplicates(tel)
        tel = self._flag_invalid_range(tel)
        tel = self._flag_per_sensor_stream(tel)

        # Drop working column
        tel = tel.drop(columns=["recorded_at_dt"])
        return tel

    def quality_summary(self, flagged_df: pd.DataFrame) -> pd.DataFrame:
        """Return a summary DataFrame of flag counts and percentages."""
        if "quality_flag" not in flagged_df.columns:
            raise ValueError("Call flag() first to produce quality_flag column.")
        counts = flagged_df["quality_flag"].value_counts().rename("count")
        pct = (counts / len(flagged_df) * 100).round(2).rename("pct")
        return pd.concat([counts, pct], axis=1).reset_index(names="quality_flag")

    # ------------------------------------------------------------------
    # Rule implementations
    # ------------------------------------------------------------------

    def _flag_duplicates(self, tel: pd.DataFrame) -> pd.DataFrame:
        """Flag exact (sensor_id, recorded_at) duplicate pairs."""
        dup_mask = tel.duplicated(subset=["sensor_id", "recorded_at_dt"], keep="first")
        self._apply_flag(tel, dup_mask, QualityFlag.DUPLICATE, "Duplicate timestamp")
        return tel

    def _flag_invalid_range(self, tel: pd.DataFrame) -> pd.DataFrame:
        """Flag values outside critical_min / critical_max bounds."""
        if self._sensor_meta.empty:
            return tel
        merged = tel.merge(
            self._sensor_meta[["critical_min", "critical_max"]],
            left_on="sensor_id",
            right_index=True,
            how="left",
        )
        out_of_range = (
            (merged["value"] < merged["critical_min"]) |
            (merged["value"] > merged["critical_max"])
        )
        # Only apply where bounds are known
        has_bounds = merged["critical_min"].notna() & merged["critical_max"].notna()
        invalid_mask = out_of_range & has_bounds
        if invalid_mask.any():
            self._apply_flag(
                tel, invalid_mask.values, QualityFlag.INVALID_RANGE,
                "Value outside critical bounds"
            )
        return tel

    def _flag_per_sensor_stream(self, tel: pd.DataFrame) -> pd.DataFrame:
        """Apply stream-level rules that need a sorted, per-sensor view."""
        # Sort once; process groups in-place by updating the original index
        tel_sorted = tel.sort_values(["asset_id", "sensor_id", "recorded_at_dt"])

        for (asset_id, sensor_id), group in tel_sorted.groupby(
            ["asset_id", "sensor_id"], sort=False
        ):
            idx = group.index
            n = len(idx)
            values = group["value"].values
            flags = tel.loc[idx, "quality_flag"].copy()
            reasons = tel.loc[idx, "quality_reason"].copy()

            # --- Insufficient history ---
            if n < self.min_history_steps:
                for i in range(n):
                    _upgrade_flag(flags, reasons, i, idx,
                                  QualityFlag.INSUFFICIENT_HISTORY,
                                  f"Only {n} readings (min={self.min_history_steps})")
                tel.loc[idx, "quality_flag"] = flags.values
                tel.loc[idx, "quality_reason"] = reasons.values
                continue

            # --- Stale: unchanged for stale_window consecutive steps ---
            stale_flags = _detect_stale(values, self.stale_window)
            for i, s in enumerate(stale_flags):
                if s:
                    _upgrade_flag(flags, reasons, i, idx,
                                  QualityFlag.STALE, "Value unchanged (stale)")

            # --- Stuck: constant within nominal band for stuck_window steps ---
            meta = self._sensor_meta.get(sensor_id)
            nom_range = 1.0
            if meta is not None:
                try:
                    nom_range = float(meta["nominal_max"]) - float(meta["nominal_min"])
                    nom_range = max(nom_range, 1e-6)
                except (TypeError, KeyError):
                    pass
            stuck_flags = _detect_stuck(values, self.stuck_window, nom_range)
            for i, s in enumerate(stuck_flags):
                if s:
                    _upgrade_flag(flags, reasons, i, idx,
                                  QualityFlag.STUCK, "Sensor stuck at constant value")

            # --- Outlier: IQR-based ---
            outlier_flags = _detect_outliers_iqr(values, self.outlier_iqr_multiplier)
            for i, s in enumerate(outlier_flags):
                if s:
                    _upgrade_flag(flags, reasons, i, idx,
                                  QualityFlag.OUTLIER, "Outlier (IQR method)")

            # --- Drift: monotonic trend over window ---
            drift_flags = _detect_drift(values, self.drift_window, nom_range,
                                        self.drift_threshold)
            for i, s in enumerate(drift_flags):
                if s:
                    _upgrade_flag(flags, reasons, i, idx,
                                  QualityFlag.DRIFT, "Monotonic drift detected")

            tel.loc[idx, "quality_flag"] = flags.values
            tel.loc[idx, "quality_reason"] = reasons.values

        return tel

    @staticmethod
    def _apply_flag(
        df: pd.DataFrame,
        mask: np.ndarray | pd.Series,
        flag: QualityFlag,
        reason: str,
    ) -> None:
        """Upgrade flag in-place for rows where mask is True."""
        mask_arr = np.asarray(mask, dtype=bool)
        current_priority = df["quality_flag"].map(
            lambda f: _FLAG_PRIORITY.get(QualityFlag(f), 0)
        )
        new_priority = _FLAG_PRIORITY[flag]
        upgrade = mask_arr & (current_priority.values < new_priority)
        df.loc[upgrade, "quality_flag"] = flag.value
        df.loc[upgrade, "quality_reason"] = reason


# ─── Vectorised detection helpers ─────────────────────────────────────────────


def _detect_stale(values: np.ndarray, window: int) -> np.ndarray:
    """Return boolean array — True where value has been identical for >= window steps."""
    n = len(values)
    result = np.zeros(n, dtype=bool)
    run = 1
    for i in range(1, n):
        if values[i] == values[i - 1]:
            run += 1
        else:
            run = 1
        if run >= window:
            result[i] = True
    return result


def _detect_stuck(values: np.ndarray, window: int, nom_range: float) -> np.ndarray:
    """Return boolean array — True where std over a rolling window is < 0.1% of nominal range."""
    n = len(values)
    result = np.zeros(n, dtype=bool)
    threshold = nom_range * 0.001  # 0.1% of nominal range
    for i in range(window - 1, n):
        seg = values[i - window + 1 : i + 1]
        if np.std(seg) < threshold:
            result[i] = True
    return result


def _detect_outliers_iqr(values: np.ndarray, multiplier: float) -> np.ndarray:
    """Return boolean array — True for values beyond Q1 - k*IQR or Q3 + k*IQR."""
    q1, q3 = np.percentile(values, 25), np.percentile(values, 75)
    iqr = q3 - q1
    if iqr < 1e-10:
        return np.zeros(len(values), dtype=bool)
    lo = q1 - multiplier * iqr
    hi = q3 + multiplier * iqr
    return (values < lo) | (values > hi)


def _detect_drift(
    values: np.ndarray,
    window: int,
    nom_range: float,
    threshold: float,
) -> np.ndarray:
    """Return boolean array — True where rolling window shows monotonic trend > threshold."""
    n = len(values)
    result = np.zeros(n, dtype=bool)
    min_change = nom_range * threshold
    for i in range(window - 1, n):
        seg = values[i - window + 1 : i + 1]
        # Monotonically increasing or decreasing beyond threshold
        net_change = abs(float(seg[-1]) - float(seg[0]))
        diffs = np.diff(seg)
        all_positive = np.all(diffs >= 0)
        all_negative = np.all(diffs <= 0)
        if (all_positive or all_negative) and net_change > min_change:
            result[i] = True
    return result


def _upgrade_flag(
    flags: pd.Series,
    reasons: pd.Series,
    i: int,
    idx: pd.Index,
    flag: QualityFlag,
    reason: str,
) -> None:
    """Upgrade the flag at position i (in the local arrays) if priority is higher."""
    current = QualityFlag(flags.iloc[i])
    if _FLAG_PRIORITY[flag] > _FLAG_PRIORITY[current]:
        flags.iloc[i] = flag.value
        reasons.iloc[i] = reason
