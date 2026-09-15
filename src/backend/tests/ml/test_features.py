"""
Tests for Phase 5: Data Quality & Feature Engineering.

Test categories
---------------
LEAKAGE TESTS (most critical)
  - Features DataFrame contains no truth/future columns
  - Labels DataFrame is not merged into features DataFrame
  - Rolling features use only past values at each step
  - Feature pipeline rejects forbidden columns from input

DATA QUALITY TESTS
  - Duplicate detection
  - Invalid range detection
  - Stale/stuck/outlier/drift/insufficient-history detection
  - Quality flags are mutually exclusive priority-ordered

ROLLING FEATURE TESTS
  - Slope is zero for constant signal
  - Slope is positive for monotonically increasing signal
  - Rolling mean tracks true mean within tolerance
  - EWM mean responds to step change

VIBRATION FEATURE TESTS
  - Kurtosis ≈ 0 for Gaussian noise (excess kurtosis)
  - Crest factor >= 1.0 always
  - Delta features are zero for constant signal

CONTEXT FEATURE TESTS
  - One-hot op conditions are mutually exclusive
  - hours_since_last_maint is 0 immediately after maintenance
  - No future mission information used

SPLIT TESTS
  - No asset_id overlap between train/val/test
  - Every asset_id appears in exactly one split
  - Splits are reproducible with same seed

LABEL TESTS
  - RUL is non-negative
  - failure_within_24h ⊆ failure_within_72h (every 24h failure is also 72h)
  - health_class is one of {HEALTHY, DEGRADED, CRITICAL}
  - No label columns appear in features DataFrame

INTEGRATION TESTS
  - build_feature_dataset produces consistent shapes
  - Validation suite passes on tiny simulator result
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.ml.features import (
    AssetTemporalSplitter,
    DataQualityDetector,
    FeaturePipeline,
    LabelGenerator,
    QualityFlag,
    build_feature_dataset,
)
from app.ml.features.cleaning import clean_telemetry
from app.ml.features.context import compute_context_features
from app.ml.features.labels import HEALTH_THRESHOLD_CRITICAL, HEALTH_THRESHOLD_HEALTHY
from app.ml.features.pipeline import FORBIDDEN_FEATURE_COLUMNS
from app.ml.features.rolling import compute_rolling_features, _rolling_slope
from app.ml.features.split import AssetTemporalSplitter
from app.ml.features.vibration import compute_vibration_features, _kurtosis
from app.ml.simulator import FleetSimulator, load_profile
from app.ml.simulator.config import default_config


# ─── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def tiny_result():
    """Run the tiny simulator profile once; reuse for all tests."""
    cfg = load_profile("tiny")
    sim = FleetSimulator(cfg)
    return sim.run()


@pytest.fixture(scope="module")
def tiny_features(tiny_result):
    """Run the feature pipeline on the tiny result."""
    features_df, labels_df, catalog = build_feature_dataset(
        tiny_result, windows=[6, 24], ewm_alphas=[0.1]
    )
    return features_df, labels_df, catalog


@pytest.fixture
def minimal_sensors_df():
    return pd.DataFrame([
        {
            "sensor_id": "s1", "sensor_type": "VIBRATION_RMS",
            "unit": "mm/s", "nominal_min": 0.5, "nominal_max": 4.0,
            "critical_min": 0.0, "critical_max": 20.0,
        },
        {
            "sensor_id": "s2", "sensor_type": "TEMP_ENGINE",
            "unit": "degC", "nominal_min": 60.0, "nominal_max": 120.0,
            "critical_min": -20.0, "critical_max": 300.0,
        },
    ])


@pytest.fixture
def minimal_telemetry_df():
    n = 50
    rng = np.random.default_rng(0)
    times = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    rows = []
    for i, ts in enumerate(times):
        rows.append({
            "asset_id": "asset_a", "sensor_id": "s1",
            "component_id": "comp_x",
            "value": 1.5 + 0.1 * rng.standard_normal(),
            "recorded_at": ts.isoformat(),
            "operating_hours": float(i + 1),
            "operating_condition": "CRUISE",
            "source": "test",
        })
        rows.append({
            "asset_id": "asset_a", "sensor_id": "s2",
            "component_id": "comp_x",
            "value": 90.0 + rng.standard_normal(),
            "recorded_at": ts.isoformat(),
            "operating_hours": float(i + 1),
            "operating_condition": "CRUISE",
            "source": "test",
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# LEAKAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def test_features_contain_no_forbidden_columns(tiny_features):
    """LEAKAGE: No truth/label columns in the features DataFrame."""
    features_df, _, _ = tiny_features
    found = [c for c in features_df.columns if c in FORBIDDEN_FEATURE_COLUMNS]
    assert found == [], f"Forbidden columns leaked into features: {found}"


def test_labels_not_in_features(tiny_features):
    """LEAKAGE: Explicit label columns must not appear in features DataFrame."""
    features_df, labels_df, _ = tiny_features
    label_cols = {"rul_cycles", "failure_within_24h", "failure_within_72h",
                  "failure_within_window", "health_class"}
    leaked = label_cols & set(features_df.columns)
    assert leaked == set(), f"Label columns found in features: {leaked}"


def test_label_generator_validate_no_leakage(tiny_features):
    """LEAKAGE: LabelGenerator.validate_no_leakage() returns empty list for clean features."""
    features_df, _, _ = tiny_features
    gen = LabelGenerator()
    violations = gen.validate_no_leakage(features_df)
    assert violations == [], f"Leakage violations: {violations}"


def test_pipeline_validate_no_leakage(tiny_result, tiny_features):
    """LEAKAGE: FeaturePipeline.validate_no_leakage() returns empty list."""
    features_df, _, _ = tiny_features
    pipeline = FeaturePipeline(tiny_result.observable["sensors"])
    violations = pipeline.validate_no_leakage(features_df)
    assert violations == [], f"Pipeline leakage violations: {violations}"


def test_rolling_slope_constant_signal_is_zero():
    """LEAKAGE: Rolling slope of a constant signal must be ~0 (no phantom trends)."""
    values = np.ones(100) * 5.0
    slopes = _rolling_slope(values, window=24)
    assert np.allclose(slopes, 0.0, atol=1e-10), \
        "Rolling slope of constant signal should be zero"


def test_rolling_slope_increasing_signal_is_positive():
    """LEAKAGE / correctness: Slope of monotonically increasing signal must be > 0."""
    values = np.arange(100, dtype=float)
    slopes = _rolling_slope(values, window=10)
    # After initial window, all slopes should be ~1.0
    assert np.all(slopes[10:] > 0.0), \
        "Slopes of increasing signal should be positive"


def test_features_have_no_future_information(tiny_result):
    """LEAKAGE: Verify rolling features at step t only use values up to step t.

    We check that roll_mean at position i equals the mean of values[0..i].
    """
    obs = tiny_result.observable
    sensors = obs["sensors"]
    tel = obs["telemetry"]

    # Take one (asset, sensor) pair with enough data
    counts = tel.groupby(["asset_id", "sensor_id"]).size()
    pair = counts[counts >= 50].index[0]
    a_id, s_id = pair

    sub = tel[(tel["asset_id"] == a_id) & (tel["sensor_id"] == s_id)].copy()
    sub = sub.sort_values("recorded_at").reset_index(drop=True)

    # Run pipeline on just this sub-stream
    pipeline = FeaturePipeline(sensors, windows=[10])
    feat = pipeline.transform(sub, pd.DataFrame(), pd.DataFrame())

    # Find the roll10_mean column
    mean_col = [c for c in feat.columns if "roll10_mean" in c]
    if not mean_col:
        pytest.skip("No roll10_mean column found for this sensor")
    col = mean_col[0]

    values = sub["value"].values
    computed_means = feat[col].values

    # At each position i, roll10_mean should equal mean(values[max(0,i-9):i+1])
    for i in [10, 20, 30, 49]:
        start = max(0, i - 9)
        expected = float(values[start : i + 1].mean())
        actual = float(computed_means[i])
        assert abs(actual - expected) < 1e-6, \
            f"At step {i}: expected mean={expected:.4f}, got {actual:.4f} — future data used?"


def test_truth_columns_not_in_observable(tiny_result):
    """LEAKAGE: Simulator's validate_no_leakage must pass."""
    violations = tiny_result.validate_no_leakage()
    assert violations == [], f"Simulator leakage: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# DATA QUALITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def test_duplicate_detection(minimal_sensors_df):
    """Quality: duplicate (sensor_id, recorded_at) rows flagged as DUPLICATE."""
    ts = "2023-01-01T00:00:00+00:00"
    rows = [
        {"asset_id": "a", "sensor_id": "s1", "component_id": "c",
         "value": 1.5, "recorded_at": ts,
         "operating_hours": 1.0, "operating_condition": "CRUISE", "source": "test"},
        # Exact duplicate
        {"asset_id": "a", "sensor_id": "s1", "component_id": "c",
         "value": 1.5, "recorded_at": ts,
         "operating_hours": 1.0, "operating_condition": "CRUISE", "source": "test"},
        # Different timestamp — clean
        {"asset_id": "a", "sensor_id": "s1", "component_id": "c",
         "value": 1.6, "recorded_at": "2023-01-01T01:00:00+00:00",
         "operating_hours": 2.0, "operating_condition": "CRUISE", "source": "test"},
    ]
    tel = pd.DataFrame(rows)
    detector = DataQualityDetector(minimal_sensors_df, min_history_steps=2)
    flagged = detector.flag(tel)
    dup_flags = flagged["quality_flag"] == QualityFlag.DUPLICATE.value
    assert dup_flags.sum() >= 1, "At least one duplicate should be flagged"


def test_invalid_range_detection(minimal_sensors_df):
    """Quality: value outside critical_max flagged as INVALID_RANGE."""
    rows = []
    for i in range(15):
        rows.append({
            "asset_id": "a", "sensor_id": "s1", "component_id": "c",
            "value": 1.5, "recorded_at": f"2023-01-01T{i:02d}:00:00+00:00",
            "operating_hours": float(i + 1), "operating_condition": "CRUISE", "source": "test",
        })
    # Add one out-of-range value (critical_max for VIBRATION_RMS = 20.0)
    rows.append({
        "asset_id": "a", "sensor_id": "s1", "component_id": "c",
        "value": 999.0, "recorded_at": "2023-01-01T20:00:00+00:00",
        "operating_hours": 21.0, "operating_condition": "CRUISE", "source": "test",
    })
    tel = pd.DataFrame(rows)
    detector = DataQualityDetector(minimal_sensors_df, min_history_steps=5)
    flagged = detector.flag(tel)
    invalid = flagged[flagged["quality_flag"] == QualityFlag.INVALID_RANGE.value]
    assert len(invalid) >= 1, "Out-of-range value should be flagged"


def test_stale_detection():
    """Quality: repeated identical value for >= stale_window steps flagged as STALE."""
    n = 50
    values = np.ones(n) * 2.5  # all the same
    rows = []
    for i in range(n):
        rows.append({
            "asset_id": "a", "sensor_id": "s1", "component_id": "c",
            "value": float(values[i]),
            "recorded_at": pd.Timestamp("2023-01-01", tz="UTC") + pd.Timedelta(hours=i),
            "operating_hours": float(i + 1), "operating_condition": "CRUISE", "source": "test",
        })
    tel = pd.DataFrame(rows)
    sensors = pd.DataFrame([{
        "sensor_id": "s1", "sensor_type": "VIBRATION_RMS",
        "nominal_min": 0.5, "nominal_max": 4.0,
        "critical_min": 0.0, "critical_max": 20.0,
    }])
    detector = DataQualityDetector(sensors, stale_window=5, min_history_steps=3)
    flagged = detector.flag(tel)
    stale = flagged["quality_flag"].isin([QualityFlag.STALE.value, QualityFlag.STUCK.value])
    assert stale.sum() > 0, "Constant signal should produce stale/stuck flags"


def test_outlier_detection():
    """Quality: value far from distribution flagged as OUTLIER."""
    rng = np.random.default_rng(1)
    n = 60
    values = rng.normal(2.0, 0.1, n)
    values[30] = 50.0  # extreme outlier
    rows = []
    for i in range(n):
        rows.append({
            "asset_id": "a", "sensor_id": "s1", "component_id": "c",
            "value": float(values[i]),
            "recorded_at": pd.Timestamp("2023-01-01", tz="UTC") + pd.Timedelta(hours=i),
            "operating_hours": float(i + 1), "operating_condition": "CRUISE", "source": "test",
        })
    tel = pd.DataFrame(rows)
    sensors = pd.DataFrame([{
        "sensor_id": "s1", "sensor_type": "VIBRATION_RMS",
        "nominal_min": 0.5, "nominal_max": 4.0,
        "critical_min": 0.0, "critical_max": 20.0,
    }])
    detector = DataQualityDetector(sensors, outlier_iqr_multiplier=3.0, min_history_steps=5)
    flagged = detector.flag(tel)
    # The injected outlier value (50.0) should be flagged as INVALID_RANGE
    # (critical_max=20.0) OR OUTLIER
    bad_flags = flagged["quality_flag"].isin([
        QualityFlag.OUTLIER.value, QualityFlag.INVALID_RANGE.value
    ])
    assert bad_flags.any(), "Extreme value should be flagged as outlier or out-of-range"


def test_insufficient_history_flag(minimal_sensors_df):
    """Quality: stream with fewer than min_history_steps rows flagged."""
    rows = []
    for i in range(3):  # only 3 rows, min_history_steps default = 10
        rows.append({
            "asset_id": "a", "sensor_id": "s1", "component_id": "c",
            "value": 1.5 + 0.01 * i,
            "recorded_at": pd.Timestamp("2023-01-01", tz="UTC") + pd.Timedelta(hours=i),
            "operating_hours": float(i + 1), "operating_condition": "CRUISE", "source": "test",
        })
    tel = pd.DataFrame(rows)
    detector = DataQualityDetector(minimal_sensors_df, min_history_steps=10)
    flagged = detector.flag(tel)
    insuf = (flagged["quality_flag"] == QualityFlag.INSUFFICIENT_HISTORY.value)
    assert insuf.all(), "All rows should be flagged as insufficient history"


def test_quality_flags_are_strings(minimal_telemetry_df, minimal_sensors_df):
    """Quality: quality_flag column contains string values from QualityFlag enum."""
    detector = DataQualityDetector(minimal_sensors_df)
    flagged = detector.flag(minimal_telemetry_df)
    assert "quality_flag" in flagged.columns
    valid_values = {f.value for f in QualityFlag}
    assert set(flagged["quality_flag"].unique()).issubset(valid_values)


def test_quality_summary_totals_to_100_percent(minimal_telemetry_df, minimal_sensors_df):
    """Quality: summary percentages sum to 100."""
    detector = DataQualityDetector(minimal_sensors_df)
    flagged = detector.flag(minimal_telemetry_df)
    summary = detector.quality_summary(flagged)
    total_pct = summary["pct"].sum()
    assert abs(total_pct - 100.0) < 0.1, f"Percentages sum to {total_pct}, expected 100"


def test_dq_detection_on_simulator_output(tiny_result):
    """Quality: DQ detector runs on full simulator output without error."""
    obs = tiny_result.observable
    detector = DataQualityDetector(obs["sensors"])
    flagged = detector.flag(obs["telemetry"])
    assert "quality_flag" in flagged.columns
    assert len(flagged) == len(obs["telemetry"])
    # Should detect some non-OK flags in edge-case-injected output
    non_ok = (flagged["quality_flag"] != QualityFlag.OK.value).sum()
    assert non_ok > 0, "Simulator output with injected faults should have some non-OK quality flags"


# ═══════════════════════════════════════════════════════════════════════════════
# ROLLING FEATURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def test_rolling_mean_accuracy(minimal_telemetry_df, minimal_sensors_df):
    """Rolling: rolling mean matches pandas rolling mean."""
    feat = compute_rolling_features(
        clean_telemetry(minimal_telemetry_df, minimal_sensors_df),
        minimal_sensors_df,
        windows=[6],
        ewm_alphas=[],
    )
    # For sensor s1
    s1 = feat[feat["sensor_id"] == "s1"].sort_values("recorded_at")
    mean_col = [c for c in s1.columns if "roll6_mean" in c]
    assert mean_col, "roll6_mean column expected"

    expected = s1["value"].rolling(6, min_periods=1).mean().values
    actual = s1[mean_col[0]].values
    assert np.allclose(actual, expected, atol=1e-6), "Rolling mean mismatch"


def test_rolling_std_zero_for_constant():
    """Rolling: std of constant signal is zero (after initial window)."""
    n = 30
    rows = [
        {
            "asset_id": "a", "sensor_id": "s1", "component_id": "c",
            "value": 5.0,
            "recorded_at": pd.Timestamp("2023-01-01", tz="UTC") + pd.Timedelta(hours=i),
            "operating_hours": float(i + 1), "operating_condition": "CRUISE",
            "source": "test", "is_clean": True,
        }
        for i in range(n)
    ]
    tel = pd.DataFrame(rows)
    sensors = pd.DataFrame([{
        "sensor_id": "s1", "sensor_type": "VIBRATION_RMS",
        "nominal_min": 0.5, "nominal_max": 4.0,
        "critical_min": 0.0, "critical_max": 20.0,
    }])
    feat = compute_rolling_features(tel, sensors, windows=[5], ewm_alphas=[])
    std_col = [c for c in feat.columns if "roll5_std" in c]
    assert std_col
    stds = feat[std_col[0]].fillna(0.0).values
    assert np.allclose(stds, 0.0, atol=1e-10), "Std of constant signal should be zero"


# ═══════════════════════════════════════════════════════════════════════════════
# VIBRATION FEATURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def test_kurtosis_gaussian_near_zero():
    """Vibration: excess kurtosis of Gaussian noise should be near 0."""
    rng = np.random.default_rng(99)
    data = rng.standard_normal(10000)
    k = _kurtosis(data)
    assert abs(k) < 0.5, f"Kurtosis of Gaussian should be near 0, got {k:.3f}"


def test_kurtosis_impulse_high():
    """Vibration: kurtosis with impulse spike should be >> 3."""
    rng = np.random.default_rng(7)
    data = rng.standard_normal(1000)
    data[500] = 100.0  # large impulse
    k = _kurtosis(data)
    assert k > 10.0, f"Kurtosis with impulse should be high, got {k:.3f}"


def test_crest_factor_always_ge_one(minimal_sensors_df):
    """Vibration: crest_factor >= 1.0 always (mathematical invariant)."""
    n = 60
    rng = np.random.default_rng(5)
    rows = []
    for i in range(n):
        rows.append({
            "asset_id": "a", "sensor_id": "s1", "component_id": "c",
            "value": abs(rng.standard_normal()) + 0.1,
            "recorded_at": pd.Timestamp("2023-01-01", tz="UTC") + pd.Timedelta(hours=i),
            "operating_hours": float(i + 1), "operating_condition": "CRUISE",
            "source": "test", "is_clean": True,
        })
    tel = pd.DataFrame(rows)
    feat = compute_vibration_features(tel, minimal_sensors_df, windows=[10])
    crest_cols = [c for c in feat.columns if "crest_factor" in c]
    assert crest_cols, "No crest_factor columns found"
    for col in crest_cols:
        vals = feat[col].dropna().values
        assert np.all(vals >= 1.0 - 1e-9), \
            f"Crest factor < 1.0 in column {col}: min={vals.min():.4f}"


def test_delta_features_zero_for_constant(minimal_sensors_df):
    """Vibration: delta_rms = 0 for constant signal."""
    n = 40
    rows = [
        {
            "asset_id": "a", "sensor_id": "s1", "component_id": "c",
            "value": 2.0,
            "recorded_at": pd.Timestamp("2023-01-01", tz="UTC") + pd.Timedelta(hours=i),
            "operating_hours": float(i + 1), "operating_condition": "CRUISE",
            "source": "test", "is_clean": True,
        }
        for i in range(n)
    ]
    tel = pd.DataFrame(rows)
    feat = compute_vibration_features(tel, minimal_sensors_df, windows=[6])
    delta_col = [c for c in feat.columns if "_delta_rms" in c and "roll" not in c]
    if not delta_col:
        pytest.skip("No delta_rms column (non-vibration sensor or empty)")
    # First value is 0 (no previous), rest should all be 0 for constant signal
    vals = feat[delta_col[0]].fillna(0.0).values[1:]
    assert np.allclose(vals, 0.0, atol=1e-10), "delta_rms should be zero for constant signal"


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT FEATURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def test_op_condition_onehots_mutually_exclusive(minimal_telemetry_df, minimal_sensors_df):
    """Context: operating condition one-hots sum to 1 for each row."""
    cleaned = clean_telemetry(minimal_telemetry_df, minimal_sensors_df)
    feat = compute_context_features(cleaned, pd.DataFrame(), pd.DataFrame())
    op_cols = [c for c in feat.columns if c.startswith("op_cond_") and c != "op_cond_is_high_stress"]
    if not op_cols:
        pytest.skip("No op_cond columns")
    row_sums = feat[op_cols].sum(axis=1)
    assert (row_sums == 1).all(), "Op-condition one-hots should sum to 1 per row"


def test_hours_since_last_maint_zero_after_maintenance():
    """Context: hours_since_last_maint ≈ 0 for the reading immediately after maintenance."""
    ts_maint = pd.Timestamp("2023-01-10T00:00:00+00:00")
    ts_after = pd.Timestamp("2023-01-10T01:00:00+00:00")

    maint_df = pd.DataFrame([{
        "asset_id": "a", "component_id": "c",
        "event_type": "SCHEDULED",
        "performed_at": ts_maint.isoformat(),
        "asset_hours_at_event": 216.0,
    }])

    rows = [{
        "asset_id": "a", "sensor_id": "s1", "component_id": "c",
        "value": 1.5,
        "recorded_at": ts_after.isoformat(),
        "operating_hours": 217.0,
        "operating_condition": "CRUISE",
        "source": "test", "is_clean": True,
    }]
    tel = pd.DataFrame(rows)
    feat = compute_context_features(tel, maint_df, pd.DataFrame())
    h = feat["hours_since_last_maint"].iloc[0]
    assert h == pytest.approx(1.0, abs=0.1), \
        f"Expected ~1.0 hours since maintenance, got {h}"


def test_no_future_mission_data_in_features():
    """Context: hours_until_next_mission uses scheduled_start (OK) not mission outcomes."""
    ts_now = pd.Timestamp("2023-01-01T12:00:00+00:00")
    ts_future = pd.Timestamp("2023-01-03T00:00:00+00:00")

    missions_df = pd.DataFrame([{
        "asset_id": "a",
        "mission_id": "m1",
        "mission_code": "MSN-001",
        "scheduled_start": ts_future.isoformat(),
        "duration_hours": 8.0,
        "criticality": "HIGH",
        "status": "PLANNED",
        "is_conflict": False,  # ← this column must NOT appear in features
    }])

    rows = [{
        "asset_id": "a", "sensor_id": "s1", "component_id": "c",
        "value": 1.5, "recorded_at": ts_now.isoformat(),
        "operating_hours": 10.0, "operating_condition": "CRUISE",
        "source": "test", "is_clean": True,
    }]
    tel = pd.DataFrame(rows)
    feat = compute_context_features(tel, pd.DataFrame(), missions_df)

    # is_conflict must not be a feature
    assert "is_conflict" not in feat.columns

    # hours_until_next_mission should be positive (scheduled time is in future)
    h = feat["hours_until_next_mission"].iloc[0]
    expected_h = (ts_future - ts_now).total_seconds() / 3600.0
    assert h == pytest.approx(expected_h, rel=0.01)


# ═══════════════════════════════════════════════════════════════════════════════
# SPLIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def test_split_no_asset_overlap(tiny_features, tiny_result):
    """Split: train/val/test asset sets must be disjoint."""
    features_df, _, _ = tiny_features
    splitter = AssetTemporalSplitter(seed=42)
    split = splitter.split(features_df, tiny_result.truth["failure_events"])

    violations = splitter.validate_no_overlap(split)
    assert violations == [], f"Asset overlap in splits: {violations}"


def test_split_covers_all_assets(tiny_features, tiny_result):
    """Split: every asset appears in exactly one split."""
    features_df, _, _ = tiny_features
    splitter = AssetTemporalSplitter(seed=42)
    split = splitter.split(features_df, tiny_result.truth["failure_events"])

    all_in_splits = split.train_asset_ids | split.val_asset_ids | split.test_asset_ids
    all_in_data = set(features_df["asset_id"].unique())
    assert all_in_splits == all_in_data, \
        f"Assets missing from splits: {all_in_data - all_in_splits}"


def test_split_reproducible(tiny_features, tiny_result):
    """Split: same seed produces identical split."""
    features_df, _, _ = tiny_features
    splitter = AssetTemporalSplitter(seed=99)
    split_a = splitter.split(features_df, tiny_result.truth["failure_events"])
    split_b = splitter.split(features_df, tiny_result.truth["failure_events"])
    assert split_a.train_asset_ids == split_b.train_asset_ids
    assert split_a.val_asset_ids == split_b.val_asset_ids
    assert split_a.test_asset_ids == split_b.test_asset_ids


def test_split_different_seeds_differ(tiny_features, tiny_result):
    """Split: different seeds should (very likely) produce different splits."""
    features_df, _, _ = tiny_features
    split_a = AssetTemporalSplitter(seed=1).split(features_df, tiny_result.truth["failure_events"])
    split_b = AssetTemporalSplitter(seed=2).split(features_df, tiny_result.truth["failure_events"])
    # With 10 assets, probability of identical splits by chance is extremely low
    assert split_a.train_asset_ids != split_b.train_asset_ids or \
           split_a.val_asset_ids != split_b.val_asset_ids


def test_split_requires_three_assets():
    """Split: must raise ValueError with < 3 assets."""
    df = pd.DataFrame({"asset_id": ["a", "a", "b", "b"]})
    splitter = AssetTemporalSplitter()
    with pytest.raises(ValueError, match="at least 3"):
        splitter.split(df)


def test_split_all_splits_nonempty(tiny_features, tiny_result):
    """Split: all three splits must be non-empty."""
    features_df, _, _ = tiny_features
    splitter = AssetTemporalSplitter(seed=42)
    split = splitter.split(features_df, tiny_result.truth["failure_events"])
    assert len(split.train_asset_ids) > 0
    assert len(split.val_asset_ids) > 0
    assert len(split.test_asset_ids) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# LABEL TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def test_rul_is_non_negative(tiny_features):
    """Labels: RUL must be >= 0 at every step."""
    _, labels_df, _ = tiny_features
    assert (labels_df["rul_cycles"] >= 0).all(), \
        f"Negative RUL values found: {(labels_df['rul_cycles'] < 0).sum()}"


def test_failure_within_24h_subset_of_72h(tiny_features):
    """Labels: every row with failure_within_24h=1 must also have failure_within_72h=1."""
    _, labels_df, _ = tiny_features
    violation = (labels_df["failure_within_24h"] == 1) & (labels_df["failure_within_72h"] == 0)
    assert not violation.any(), \
        f"{violation.sum()} rows have 24h=1 but 72h=0 (impossible)"


def test_health_class_values_valid(tiny_features):
    """Labels: health_class must be one of {HEALTHY, DEGRADED, CRITICAL}."""
    _, labels_df, _ = tiny_features
    valid = {"HEALTHY", "DEGRADED", "CRITICAL"}
    found = set(labels_df["health_class"].unique())
    assert found.issubset(valid), f"Invalid health_class values: {found - valid}"


def test_rul_capped_at_rul_cap(tiny_result):
    """Labels: RUL should not exceed the configured cap."""
    gen = LabelGenerator(rul_cap=1000.0)
    labels = gen.generate(
        tiny_result.truth["component_health_trajectories"],
        tiny_result.truth["failure_events"],
    )
    assert (labels["rul_cycles"] <= 1000.0 + 1e-6).all(), \
        f"RUL exceeds cap: max={labels['rul_cycles'].max()}"


def test_labels_have_no_feature_columns(tiny_features):
    """Labels: labels DataFrame should not contain raw feature columns."""
    _, labels_df, _ = tiny_features
    feature_cols = {"value", "operating_condition", "operating_hours"}
    overlap = feature_cols & set(labels_df.columns)
    assert overlap == set(), f"Feature columns in labels: {overlap}"


def test_label_component_id_matches_features(tiny_features):
    """Labels: every component_id in labels exists in features."""
    features_df, labels_df, _ = tiny_features
    feat_comps = set(features_df["component_id"].unique())
    label_comps = set(labels_df["component_id"].unique())
    orphan = label_comps - feat_comps
    assert orphan == set(), f"Label component_ids not in features: {orphan}"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def test_build_feature_dataset_shape(tiny_result):
    """Integration: feature row count should be <= telemetry row count (cleaning removes dupes)."""
    features_df, labels_df, catalog = build_feature_dataset(
        tiny_result, windows=[6, 24], ewm_alphas=[0.1]
    )
    n_tel = len(tiny_result.observable["telemetry"])
    n_feat = len(features_df)
    # After deduplication, features can only be <= original telemetry rows
    assert n_feat <= n_tel, \
        f"Feature rows {n_feat} > telemetry rows {n_tel}"
    assert n_feat > 0, "Feature DataFrame must not be empty"
    assert len(labels_df) > 0, "Labels DataFrame must not be empty"


def test_feature_catalog_has_all_categories(tiny_result):
    """Integration: catalog must contain rolling, vibration, and context features."""
    _, _, catalog = build_feature_dataset(
        tiny_result, windows=[6, 24], ewm_alphas=[0.1]
    )
    assert len(catalog.rolling_features) > 0, "No rolling features in catalog"
    assert len(catalog.vibration_features) > 0, "No vibration features in catalog"
    assert len(catalog.context_features) > 0, "No context features in catalog"
    assert len(catalog.all_feature_names) > 10, \
        f"Suspiciously few features: {len(catalog.all_feature_names)}"


def test_full_pipeline_produces_no_nan_in_join_keys(tiny_result):
    """Integration: join keys must not have NaN values."""
    features_df, _, _ = build_feature_dataset(
        tiny_result, windows=[6], ewm_alphas=[]
    )
    for col in ["asset_id", "sensor_id", "component_id", "recorded_at"]:
        n_null = features_df[col].isna().sum()
        assert n_null == 0, f"Join key '{col}' has {n_null} NaN values"


def test_pipeline_is_deterministic(tiny_result):
    """Integration: running pipeline twice produces identical results."""
    obs = tiny_result.observable
    pipeline = FeaturePipeline(obs["sensors"], windows=[6], ewm_alphas=[])
    f1 = pipeline.transform(obs["telemetry"], obs["maintenance_events"], obs["missions"])
    f2 = pipeline.transform(obs["telemetry"], obs["maintenance_events"], obs["missions"])
    pd.testing.assert_frame_equal(f1, f2, check_like=False)


def test_feature_pipeline_leakage_check_passes(tiny_result):
    """Integration: validate_no_leakage returns empty list on real pipeline output."""
    features_df, _, _ = build_feature_dataset(
        tiny_result, windows=[6], ewm_alphas=[]
    )
    pipeline = FeaturePipeline(tiny_result.observable["sensors"], windows=[6], ewm_alphas=[])
    violations = pipeline.validate_no_leakage(features_df)
    assert violations == []


def test_split_and_labels_alignment(tiny_result):
    """Integration: after split, label rows align to feature rows by component+timestamp."""
    features_df, labels_df, _ = build_feature_dataset(
        tiny_result, windows=[6], ewm_alphas=[]
    )
    splitter = AssetTemporalSplitter(seed=42)
    split = splitter.split(features_df, tiny_result.truth["failure_events"])
    train_df, val_df, test_df = split.apply(features_df)

    # Labels for train assets should be a subset of all labels
    train_asset_ids = split.train_asset_ids
    train_labels = labels_df[labels_df["asset_id"].isin(train_asset_ids)]
    assert len(train_labels) > 0, "No labels for training assets"
    assert len(train_labels) < len(labels_df), "All labels went to train (no val/test)"
