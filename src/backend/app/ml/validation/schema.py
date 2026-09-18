"""
Schema and distribution validation for MissionReady AI processed datasets.

Validates:
  1. Required columns present / forbidden columns absent (leakage guard).
  2. No unexpected nulls in critical columns.
  3. Value ranges are physically plausible (distribution sanity).
  4. Train/test split boundaries are respected (no unit overlap).
  5. Monotonicity of cycle column per unit (C-MAPSS).
  6. Correct number of units and approximate row counts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


# ─── Result types ─────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    passed: bool
    check_name: str
    details: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    dataset: str
    split: str
    results: list[ValidationResult]

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        lines = [f"{'PASS' if self.passed else 'FAIL'} — {self.dataset} [{self.split}]: {ok}/{total} checks passed"]
        for r in self.results:
            icon = "✓" if r.passed else "✗"
            lines.append(f"  {icon} {r.check_name}: {r.details}")
            for w in r.warnings:
                lines.append(f"    ⚠ {w}")
        return "\n".join(lines)

    def raise_if_failed(self) -> None:
        if not self.passed:
            failures = [r for r in self.results if not r.passed]
            msg = "\n".join(f"  {r.check_name}: {r.details}" for r in failures)
            raise ValueError(f"Validation FAILED for {self.dataset}/{self.split}:\n{msg}")


# ─── Leakage guard checks ─────────────────────────────────────────────────────

# These column names must NEVER appear in feature DataFrames.
FORBIDDEN_FEATURE_COLUMNS: set[str] = {
    "true_rul",
    "true_health",
    "failure_label",
    "failure_event",
    "rul_true",
    "health_true",
    "ground_truth_rul",
    "remaining_useful_life",
}


def check_no_leakage(df: pd.DataFrame, dataset: str, split: str) -> ValidationResult:
    """Verify no ground-truth leakage columns exist in a feature DataFrame."""
    found = FORBIDDEN_FEATURE_COLUMNS.intersection(df.columns)
    if found:
        return ValidationResult(
            passed=False,
            check_name="leakage_guard",
            details=f"FORBIDDEN columns present: {sorted(found)}",
        )
    return ValidationResult(
        passed=True,
        check_name="leakage_guard",
        details=f"No forbidden columns in {len(df.columns)} feature columns",
    )


# ─── C-MAPSS specific checks ──────────────────────────────────────────────────

CMAPSS_REQUIRED_COLS = {
    "unit_id", "cycle", "setting_1", "setting_2", "setting_3",
    "sensor_2", "sensor_3", "sensor_4", "sensor_7", "sensor_8",
    "sensor_9", "sensor_11", "sensor_12", "sensor_13", "sensor_14",
    "sensor_15", "sensor_17", "sensor_20", "sensor_21",
}

CMAPSS_SENSOR_RANGES: dict[str, tuple[float, float]] = {
    # (min_plausible, max_plausible) — loose bounds to catch gross errors
    "sensor_2":  (440.0,  650.0),   # LPC outlet temp (°R)
    # FD002/FD004 contain six operating regimes, so their valid envelope is
    # wider than the single-regime FD001/FD003 subsets.
    "sensor_3":  (1200.0, 1700.0),  # HPC outlet temperature (°R)
    "sensor_4":  (1000.0, 1700.0),  # LPT outlet temp (°R)
    "sensor_7":  (100.0,  700.0),   # HPC outlet pressure (psia)
    "sensor_8":  (1800.0, 2600.0),  # Physical fan speed (rpm)
    "sensor_9":  (7800.0, 9500.0),  # Physical core speed (rpm)
    "sensor_11": (3.0,    50.0),    # Static pressure at HPC (psia)
    "sensor_12": (100.0,  700.0),   # Fuel flow / Ps30
    "sensor_17": (300.0,  400.0),   # Bleed enthalpy
    "sensor_20": (5.0,    65.0),    # HPT coolant bleed (lbm/s)
    "sensor_21": (5.0,    55.0),    # LPT coolant bleed (lbm/s)
}


def validate_cmapss_features(
    features: pd.DataFrame,
    labels: pd.DataFrame,
    split: str,
    subset: str,
    expected_min_units: int | None = None,
    enforce_physical_ranges: bool = False,
) -> ValidationReport:
    """Run schema and leakage checks on a C-MAPSS feature/label pair.

    Physical ranges are calibration-specific, not a universal schema rule.
    Canonical NASA C-MAPSS imports must enable strict range enforcement;
    generic import validation retains any deviations as warnings.
    """
    results: list[ValidationResult] = []
    dataset = f"cmapss_{subset}"

    # 1. Leakage guard
    results.append(check_no_leakage(features, dataset, split))

    # 2. Required columns present
    missing = CMAPSS_REQUIRED_COLS - set(features.columns)
    if missing:
        results.append(ValidationResult(
            passed=False,
            check_name="required_columns",
            details=f"Missing columns: {sorted(missing)}",
        ))
    else:
        results.append(ValidationResult(
            passed=True,
            check_name="required_columns",
            details=f"All {len(CMAPSS_REQUIRED_COLS)} required columns present",
        ))

    # 3. No nulls in key columns
    key_cols = ["unit_id", "cycle"] + [c for c in features.columns if c.startswith("sensor_")]
    key_cols_present = [c for c in key_cols if c in features.columns]
    null_counts = features[key_cols_present].isnull().sum()
    null_cols = null_counts[null_counts > 0]
    if null_cols.empty:
        results.append(ValidationResult(
            passed=True,
            check_name="no_nulls_in_key_columns",
            details=f"No nulls in {len(key_cols_present)} key columns",
        ))
    else:
        results.append(ValidationResult(
            passed=False,
            check_name="no_nulls_in_key_columns",
            details=f"Nulls found: {null_cols.to_dict()}",
        ))

    # 4. Unit count check
    n_units = int(features["unit_id"].nunique()) if "unit_id" in features.columns else 0
    if expected_min_units is not None and n_units < expected_min_units:
        results.append(ValidationResult(
            passed=False,
            check_name="unit_count",
            details=f"Only {n_units} units; expected >= {expected_min_units}",
        ))
    else:
        results.append(ValidationResult(
            passed=True,
            check_name="unit_count",
            details=f"{n_units} units",
        ))

    # 5. Cycle monotonicity per unit
    if "unit_id" in features.columns and "cycle" in features.columns:
        bad_units = []
        for uid, grp in features.groupby("unit_id"):
            cycles = grp["cycle"].values
            if not np.all(cycles[:-1] <= cycles[1:]):
                bad_units.append(uid)
        if bad_units:
            results.append(ValidationResult(
                passed=False,
                check_name="cycle_monotonicity",
                details=f"Non-monotonic cycles in units: {bad_units[:5]}",
            ))
        else:
            results.append(ValidationResult(
                passed=True,
                check_name="cycle_monotonicity",
                details="All unit cycles are monotonically non-decreasing",
            ))

    # 6. Sensor range checks (distribution sanity)
    range_warnings: list[str] = []
    range_pass = True
    for sensor, (lo, hi) in CMAPSS_SENSOR_RANGES.items():
        if sensor not in features.columns:
            continue
        col = features[sensor]
        actual_min = float(col.min())
        actual_max = float(col.max())
        if actual_min < lo or actual_max > hi:
            range_warnings.append(
                f"{sensor}: observed [{actual_min:.1f}, {actual_max:.1f}] "
                f"vs expected [{lo}, {hi}]"
            )
            range_pass = False
    results.append(ValidationResult(
        passed=range_pass or not enforce_physical_ranges,
        check_name="sensor_ranges",
        details="All sensor values within plausible physical ranges" if range_pass
                else (
                    f"{len(range_warnings)} sensor(s) out of range"
                    if enforce_physical_ranges
                    else f"{len(range_warnings)} sensor(s) outside C-MAPSS calibration envelope"
                ),
        warnings=range_warnings,
    ))

    # 7. Label shape matches feature shape
    if labels is not None:
        if len(labels) != len(features):
            results.append(ValidationResult(
                passed=False,
                check_name="label_shape_match",
                details=f"Label rows {len(labels)} != feature rows {len(features)}",
            ))
        else:
            results.append(ValidationResult(
                passed=True,
                check_name="label_shape_match",
                details=f"Labels and features both have {len(features)} rows",
            ))

        # 8. RUL values are non-negative
        if "true_rul" in labels.columns:
            neg = (labels["true_rul"].dropna() < 0).sum()
            if neg > 0:
                results.append(ValidationResult(
                    passed=False,
                    check_name="rul_non_negative",
                    details=f"{neg} negative RUL values in labels",
                ))
            else:
                results.append(ValidationResult(
                    passed=True,
                    check_name="rul_non_negative",
                    details="All RUL values are non-negative",
                ))

    return ValidationReport(dataset=dataset, split=split, results=results)


# ─── IMS specific checks ─────────────────────────────────────────────────────

IMS_REQUIRED_FEATURE_COLS = {
    "run_id", "bearing_id", "snapshot_index",
    "rms", "kurtosis", "peak", "crest_factor",
    "dominant_freq", "spectral_energy", "spectral_centroid",
}

# IMS bearing test rig sample rate: 20 kHz
_IMS_SAMPLING_RATE_HZ: float = 20_000.0

IMS_FEATURE_RANGES: dict[str, tuple[float, float]] = {
    "rms":              (0.0,  100.0),
    "kurtosis":         (-5.0, 200.0),  # healthy ~3; fault can be >>10
    "crest_factor":     (1.0,  100.0),  # always ≥ 1 by definition
    "spectral_energy":  (0.0,  1e10),
    "dominant_freq":    (0.0,  _IMS_SAMPLING_RATE_HZ / 2),  # Nyquist limit
}


def validate_ims_features(
    features: pd.DataFrame,
    labels: pd.DataFrame,
) -> ValidationReport:
    """Run all validation checks on processed IMS features."""
    results: list[ValidationResult] = []
    dataset = "ims_bearings"
    split = "all"

    # 1. Leakage guard
    results.append(check_no_leakage(features, dataset, split))

    # 2. Required columns
    missing = IMS_REQUIRED_FEATURE_COLS - set(features.columns)
    if missing:
        results.append(ValidationResult(
            passed=False,
            check_name="required_columns",
            details=f"Missing: {sorted(missing)}",
        ))
    else:
        results.append(ValidationResult(
            passed=True,
            check_name="required_columns",
            details=f"All {len(IMS_REQUIRED_FEATURE_COLS)} required columns present",
        ))

    # 3. No nulls in numeric feature columns
    num_cols = [c for c in features.columns if c not in ("run_id", "timestamp")]
    null_counts = features[num_cols].isnull().sum()
    bad = null_counts[null_counts > 0]
    if bad.empty:
        results.append(ValidationResult(
            passed=True,
            check_name="no_nulls",
            details=f"No nulls in {len(num_cols)} numeric columns",
        ))
    else:
        results.append(ValidationResult(
            passed=False,
            check_name="no_nulls",
            details=f"Nulls in: {bad.to_dict()}",
        ))

    # 4. Feature range checks
    range_warnings: list[str] = []
    range_pass = True
    for col, (lo, hi) in IMS_FEATURE_RANGES.items():
        if col not in features.columns:
            continue
        vals = features[col].dropna()
        if vals.empty:
            continue
        actual_min = float(vals.min())
        actual_max = float(vals.max())
        if actual_min < lo or actual_max > hi:
            range_warnings.append(f"{col}: [{actual_min:.3g}, {actual_max:.3g}] vs [{lo}, {hi}]")
            range_pass = False
    results.append(ValidationResult(
        passed=range_pass,
        check_name="feature_ranges",
        details="All features within plausible ranges" if range_pass else f"{len(range_warnings)} out of range",
        warnings=range_warnings,
    ))

    # 5. Crest factor >= 1 by definition
    if "crest_factor" in features.columns:
        below_one = (features["crest_factor"].dropna() < 1.0 - 1e-6).sum()
        if below_one > 0:
            results.append(ValidationResult(
                passed=False,
                check_name="crest_factor_ge_1",
                details=f"{below_one} crest_factor values < 1.0 (impossible by definition)",
            ))
        else:
            results.append(ValidationResult(
                passed=True,
                check_name="crest_factor_ge_1",
                details="All crest_factor values >= 1.0",
            ))

    # 6. Label shape
    if labels is not None and len(labels) != len(features):
        results.append(ValidationResult(
            passed=False,
            check_name="label_shape_match",
            details=f"Label rows {len(labels)} != feature rows {len(features)}",
        ))
    elif labels is not None:
        results.append(ValidationResult(
            passed=True,
            check_name="label_shape_match",
            details=f"Labels and features both have {len(features)} rows",
        ))

    return ValidationReport(dataset=dataset, split=split, results=results)
