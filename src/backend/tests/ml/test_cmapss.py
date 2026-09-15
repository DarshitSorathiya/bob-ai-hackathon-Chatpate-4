"""
Tests for C-MAPSS parser, preprocessing, validation, and leakage guard.

These tests use SYNTHETIC data that mimics the C-MAPSS structure — they do NOT
require the real dataset to be downloaded. They verify:

  1. Parser correctly assigns column names and types.
  2. Rolling features are computed per-unit (no cross-boundary leakage).
  3. true_rul is NEVER present in the feature DataFrame (leakage guard).
  4. RUL labels are non-negative and capped correctly.
  5. Test-split RUL assignment is correct (only last cycle per unit).
  6. Validation report passes on clean data.
  7. Validation report fails on deliberately corrupted data.
  8. Provenance sidecar is written with expected fields.
"""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add src/backend to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.ml.ingestion.cmapss import (
    CMAPSSSubset,
    CMAPSS_COLUMNS,
    SENSOR_COLS,
    SETTING_COLS,
    add_rolling_features,
    compute_rul_labels,
    load_cmapss_subset,
    normalise_operating_conditions,
    parse_cmapss_file,
    preprocess_cmapss,
    save_cmapss_features,
)
from app.ml.ingestion.provenance import (
    PROVENANCE_SCHEMA_VERSION,
    load_provenance,
    write_provenance,
)
from app.ml.validation.schema import (
    FORBIDDEN_FEATURE_COLUMNS,
    check_no_leakage,
    validate_cmapss_features,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_cmapss_raw(n_units: int = 5, cycles_per_unit: int = 20) -> str:
    """Generate a minimal C-MAPSS-like text file as a string."""
    rng = np.random.default_rng(42)
    lines = []
    for unit in range(1, n_units + 1):
        for cycle in range(1, cycles_per_unit + 1):
            s1, s2, s3 = 25.0, 0.84, 100.0
            sensors = rng.uniform(300.0, 1500.0, size=21).tolist()
            row = [unit, cycle, s1, s2, s3] + sensors
            lines.append("  ".join(f"{v:.4f}" for v in row))
    return "\n".join(lines)


def _make_cmapss_files(tmp_path: Path, subset: str, n_units: int = 5, cycles: int = 20):
    """Write train, test, and RUL files for one C-MAPSS subset."""
    raw = _make_cmapss_raw(n_units, cycles)
    # All three files use same format; RUL file has one value per unit
    (tmp_path / f"train_{subset}.txt").write_text(raw)
    (tmp_path / f"test_{subset}.txt").write_text(raw)
    rul_values = "\n".join(str(np.random.randint(10, 100)) for _ in range(n_units))
    (tmp_path / f"RUL_{subset}.txt").write_text(rul_values)


# ─── Parser tests ─────────────────────────────────────────────────────────────

def test_parse_assigns_correct_column_names(tmp_path):
    _make_cmapss_files(tmp_path, "FD001")
    df = parse_cmapss_file(tmp_path / "train_FD001.txt")
    assert list(df.columns) == CMAPSS_COLUMNS


def test_parse_correct_dtypes(tmp_path):
    _make_cmapss_files(tmp_path, "FD001")
    df = parse_cmapss_file(tmp_path / "train_FD001.txt")
    assert df["unit_id"].dtype == np.int32
    assert df["cycle"].dtype == np.int32
    for col in SENSOR_COLS + SETTING_COLS:
        assert df[col].dtype == np.float32, f"{col} should be float32"


def test_parse_no_nulls(tmp_path):
    _make_cmapss_files(tmp_path, "FD001")
    df = parse_cmapss_file(tmp_path / "train_FD001.txt")
    assert df.isnull().sum().sum() == 0


def test_parse_wrong_column_count_raises(tmp_path):
    bad_file = tmp_path / "bad.txt"
    bad_file.write_text("1 2 3\n4 5 6\n")  # only 3 columns
    with pytest.raises(ValueError, match="Unexpected column count"):
        parse_cmapss_file(bad_file)


def test_parse_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_cmapss_file(Path("/nonexistent/train_FD001.txt"))


def test_load_cmapss_subset_structure(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=5, cycles=20)
    subset = load_cmapss_subset(tmp_path, "FD001")
    assert subset.subset == "FD001"
    assert subset.train_units == 5
    assert subset.test_units == 5
    assert len(subset.rul_test) == 5
    assert subset.train.shape[1] == 26


def test_load_cmapss_subset_rul_mismatch_raises(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=5, cycles=20)
    # Write RUL with wrong number of values
    (tmp_path / "RUL_FD001.txt").write_text("10\n20\n30\n")  # only 3, need 5
    with pytest.raises(ValueError, match="RUL vector length"):
        load_cmapss_subset(tmp_path, "FD001")


# ─── RUL label tests ──────────────────────────────────────────────────────────

def test_rul_labels_are_non_negative(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=3, cycles=30)
    raw = parse_cmapss_file(tmp_path / "train_FD001.txt")
    labels = compute_rul_labels(raw, rul_cap=125)
    assert (labels >= 0).all(), "RUL labels must be non-negative"


def test_rul_labels_capped_at_rul_cap(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=3, cycles=200)
    raw = parse_cmapss_file(tmp_path / "train_FD001.txt")
    labels = compute_rul_labels(raw, rul_cap=125)
    assert (labels <= 125).all(), "RUL labels must not exceed rul_cap"


def test_rul_labels_zero_at_last_cycle(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=2, cycles=50)
    raw = parse_cmapss_file(tmp_path / "train_FD001.txt")
    labels = compute_rul_labels(raw, rul_cap=125)
    for unit_id, grp in raw.groupby("unit_id"):
        last_idx = grp.index[-1]
        assert labels.loc[last_idx] == 0.0, f"RUL at last cycle of unit {unit_id} must be 0"


def test_rul_labels_same_index_as_features(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=3, cycles=20)
    raw = parse_cmapss_file(tmp_path / "train_FD001.txt")
    labels = compute_rul_labels(raw, rul_cap=125)
    assert list(labels.index) == list(raw.index)


# ─── Leakage guard tests (CRITICAL) ──────────────────────────────────────────

def test_true_rul_never_in_feature_dataframe(tmp_path):
    """Core leakage guard: true_rul must be absent from feature DataFrame."""
    _make_cmapss_files(tmp_path, "FD001", n_units=5, cycles=30)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    for split, cf in processed.items():
        assert "true_rul" not in cf.features.columns, (
            f"LEAKAGE: true_rul found in {split} feature DataFrame"
        )


def test_forbidden_columns_absent_from_features(tmp_path):
    """All FORBIDDEN_FEATURE_COLUMNS must be absent from processed features."""
    _make_cmapss_files(tmp_path, "FD001", n_units=3, cycles=20)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    for split, cf in processed.items():
        found = FORBIDDEN_FEATURE_COLUMNS.intersection(cf.features.columns)
        assert not found, f"Forbidden columns in {split} features: {found}"


def test_labels_contain_true_rul(tmp_path):
    """Labels DataFrame must have the true_rul column."""
    _make_cmapss_files(tmp_path, "FD001", n_units=3, cycles=20)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    assert "true_rul" in processed["train"].labels.columns
    assert "true_rul" in processed["test"].labels.columns


def test_validation_leakage_check_fails_on_injected_true_rul(tmp_path):
    """Validate that check_no_leakage catches injected true_rul."""
    _make_cmapss_files(tmp_path, "FD001", n_units=3, cycles=20)
    df = parse_cmapss_file(tmp_path / "train_FD001.txt")
    # Deliberately inject the forbidden column
    df["true_rul"] = 50.0
    result = check_no_leakage(df, "test_dataset", "train")
    assert not result.passed, "check_no_leakage must FAIL when true_rul is present"


def test_validation_leakage_check_passes_on_clean_features(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=3, cycles=20)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    result = check_no_leakage(processed["train"].features, "cmapss_FD001", "train")
    assert result.passed, "Leakage check must pass on clean features"


# ─── Rolling features tests ───────────────────────────────────────────────────

def test_rolling_features_respect_unit_boundaries(tmp_path):
    """Rolling statistics must be computed per unit, not across unit boundaries."""
    _make_cmapss_files(tmp_path, "FD001", n_units=4, cycles=15)
    raw = parse_cmapss_file(tmp_path / "train_FD001.txt")
    feat = add_rolling_features(raw, window=5)

    # For each unit, the first cycle's rolling mean must equal the raw sensor value
    # (window of 1, since min_periods=1)
    for unit_id, grp in feat.groupby("unit_id"):
        first_row = grp.sort_values("cycle").iloc[0]
        assert abs(first_row["sensor_2_mean"] - first_row["sensor_2"]) < 1e-3, (
            f"Unit {unit_id}: rolling mean at first cycle should equal raw value"
        )


def test_rolling_features_adds_expected_columns(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=2, cycles=10)
    raw = parse_cmapss_file(tmp_path / "train_FD001.txt")
    feat = add_rolling_features(raw, window=3)
    # At least one informative sensor should have rolling columns
    assert "sensor_2_mean" in feat.columns
    assert "sensor_2_std" in feat.columns
    assert "sensor_2_trend" in feat.columns


def test_no_nulls_after_rolling_features(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=3, cycles=20)
    raw = parse_cmapss_file(tmp_path / "train_FD001.txt")
    feat = add_rolling_features(raw, window=10)
    null_count = feat.isnull().sum().sum()
    assert null_count == 0, f"Rolling features produced {null_count} null values"


# ─── Preprocess pipeline tests ────────────────────────────────────────────────

def test_preprocess_returns_train_and_test_splits(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=5, cycles=20)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    assert "train" in processed
    assert "test" in processed


def test_preprocess_feature_and_label_rows_match(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=5, cycles=20)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    for split, cf in processed.items():
        assert len(cf.features) == len(cf.labels), (
            f"Feature/label row mismatch in {split}: "
            f"{len(cf.features)} != {len(cf.labels)}"
        )


def test_preprocess_test_rul_at_last_cycle_only(tmp_path):
    """For test split, known RUL must be at last cycle per unit only; others NaN."""
    _make_cmapss_files(tmp_path, "FD001", n_units=5, cycles=15)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=3)
    test_cf = processed["test"]

    for unit_id, grp in test_cf.features.groupby("unit_id"):
        last_idx = grp.sort_values("cycle").index[-1]
        rul_at_last = test_cf.labels.loc[last_idx, "true_rul"]
        assert not np.isnan(rul_at_last), f"Unit {unit_id}: last cycle RUL should not be NaN"
        # All other cycles should be NaN
        other_idxs = grp.index.difference([last_idx])
        if len(other_idxs) > 0:
            rul_others = test_cf.labels.loc[other_idxs, "true_rul"]
            assert rul_others.isna().all(), (
                f"Unit {unit_id}: non-last cycles should have NaN RUL"
            )


# ─── Validation report tests ──────────────────────────────────────────────────

def test_validation_passes_on_well_formed_data(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=5, cycles=30)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    for split, cf in processed.items():
        report = validate_cmapss_features(
            cf.features, cf.labels, split=split, subset="FD001", expected_min_units=5,
        )
        assert report.passed, f"Validation failed for {split}:\n{report.summary()}"


def test_validation_fails_on_insufficient_units(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=3, cycles=20)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    report = validate_cmapss_features(
        processed["train"].features, processed["train"].labels,
        split="train", subset="FD001", expected_min_units=100,
    )
    assert not report.passed, "Validation should fail when unit count is below minimum"


def test_validation_fails_on_negative_rul(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=3, cycles=20)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    # Inject negative RUL into labels
    bad_labels = processed["train"].labels.copy()
    bad_labels.loc[bad_labels.index[0], "true_rul"] = -5.0
    report = validate_cmapss_features(
        processed["train"].features, bad_labels,
        split="train", subset="FD001",
    )
    assert not report.passed, "Validation should fail on negative RUL values"


# ─── Save + provenance tests ──────────────────────────────────────────────────

def test_save_produces_expected_parquet_files(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=5, cycles=20)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    out_dir = tmp_path / "processed"
    paths = save_cmapss_features(processed, out_dir)

    assert (out_dir / "cmapss_fd001_train_features.parquet").exists()
    assert (out_dir / "cmapss_fd001_train_labels.parquet").exists()
    assert (out_dir / "cmapss_fd001_test_features.parquet").exists()
    assert (out_dir / "cmapss_fd001_test_labels.parquet").exists()


def test_saved_parquet_can_be_reloaded_without_corruption(tmp_path):
    _make_cmapss_files(tmp_path, "FD001", n_units=5, cycles=20)
    subset_data = load_cmapss_subset(tmp_path, "FD001")
    processed = preprocess_cmapss(subset_data, rul_cap=125, rolling_window=5)
    out_dir = tmp_path / "processed"
    save_cmapss_features(processed, out_dir)

    reloaded = pd.read_parquet(out_dir / "cmapss_fd001_train_features.parquet")
    assert len(reloaded) == len(processed["train"].features)
    assert "true_rul" not in reloaded.columns, "LEAKAGE: true_rul survived round-trip to Parquet"


def test_provenance_sidecar_written_correctly(tmp_path):
    out_file = tmp_path / "test_output.parquet"
    out_file.write_bytes(b"fake parquet content")
    source = tmp_path / "source.txt"
    source.write_text("raw data")

    prov_path = write_provenance(
        dataset_id="cmapss_fd001",
        output_path=out_file,
        source_paths=[source],
        pipeline_version="1.0.0",
        parameters={"rul_cap": 125, "rolling_window": 15},
        notes="Test note",
        compute_checksums=True,
    )

    assert prov_path.exists()
    with prov_path.open() as fh:
        prov = json.load(fh)

    assert prov["schema_version"] == PROVENANCE_SCHEMA_VERSION
    assert prov["dataset_id"] == "cmapss_fd001"
    assert prov["pipeline_version"] == "1.0.0"
    assert prov["parameters"]["rul_cap"] == 125
    assert len(prov["source_files"]) == 1
    assert prov["source_files"][0]["sha256"] is not None
    assert prov["output_sha256"] is not None


def test_load_provenance_returns_none_when_absent(tmp_path):
    out_file = tmp_path / "orphan.parquet"
    result = load_provenance(out_file)
    assert result is None


def test_load_provenance_returns_dict_when_present(tmp_path):
    out_file = tmp_path / "output.parquet"
    out_file.write_bytes(b"data")
    write_provenance(
        dataset_id="cmapss_fd001",
        output_path=out_file,
        source_paths=[],
        pipeline_version="1.0.0",
        parameters={},
        compute_checksums=False,
    )
    result = load_provenance(out_file)
    assert isinstance(result, dict)
    assert result["dataset_id"] == "cmapss_fd001"
