"""
NASA C-MAPSS Turbofan Engine Degradation Simulation — Parser and Preprocessor.

Dataset contract
----------------
Each C-MAPSS file is whitespace-delimited with no header row.
Column layout (26 columns):

  0  unit_id          — engine (trajectory) identifier
  1  cycle            — operational cycle number (1-based)
  2  setting_1        — operational setting 1
  3  setting_2        — operational setting 2
  4  setting_3        — operational setting 3
  5  sensor_1         — (T2)  Total temperature at fan inlet
  6  sensor_2         — (T24) Total temperature at LPC outlet
  7  sensor_3         — (T30) Total temperature at HPC outlet
  8  sensor_4         — (T50) Total temperature at LPT outlet
  9  sensor_5         — (P2)  Pressure at fan inlet
 10  sensor_6         — (P15) Total pressure in bypass-duct
 11  sensor_7         — (P30) Total pressure at HPC outlet
 12  sensor_8         — (Nf)  Physical fan speed
 13  sensor_9         — (Nc)  Physical core speed
 14  sensor_10        — (epr) Engine pressure ratio
 15  sensor_11        — (Ps30) Static pressure at HPC outlet
 16  sensor_12        — (phi) Ratio of fuel flow to Ps30
 17  sensor_13        — (NRf) Corrected fan speed
 18  sensor_14        — (NRc) Corrected core speed
 19  sensor_15        — (BPR) Bypass Ratio
 20  sensor_16        — (farB) Burner fuel-air ratio
 21  sensor_17        — (htBleed) Bleed Enthalpy
 22  sensor_18        — (Nf_dmd) Demanded fan speed
 23  sensor_19        — (PCNfR_dmd) Demanded corrected fan speed
 24  sensor_20        — (W31) HPT coolant bleed
 25  sensor_21        — (W32) LPT coolant bleed

RUL convention
--------------
- Training data: trajectories run to failure. True RUL is inferred as
  (max_cycle_for_unit - current_cycle). A piecewise-linear cap
  (default 125 cycles) is applied so that early healthy cycles do not dominate.
- Test data: trajectories are truncated before failure.
  True RUL at the last cycle is given in the RUL_FDxxx.txt file.

Leakage guard
-------------
true_rul is stored in a SEPARATE column and must NEVER be used as a model feature.
The preprocessing pipeline outputs:
  - A feature DataFrame (no true_rul column).
  - A labels DataFrame (true_rul only) indexed identically.
These are written to separate Parquet files so the ML pipeline cannot
accidentally join them as features.

References
----------
A. Saxena and K. Goebel (2008), "Turbofan Engine Degradation Simulation Data Set",
NASA Ames Prognostics Data Repository, Moffett Field, CA.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

CMAPSS_COLUMNS: list[str] = [
    "unit_id", "cycle",
    "setting_1", "setting_2", "setting_3",
    "sensor_1", "sensor_2", "sensor_3", "sensor_4", "sensor_5",
    "sensor_6", "sensor_7", "sensor_8", "sensor_9", "sensor_10",
    "sensor_11", "sensor_12", "sensor_13", "sensor_14", "sensor_15",
    "sensor_16", "sensor_17", "sensor_18", "sensor_19", "sensor_20",
    "sensor_21",
]

SETTING_COLS = ["setting_1", "setting_2", "setting_3"]
SENSOR_COLS = [f"sensor_{i}" for i in range(1, 22)]

# Sensors that carry near-zero variance across all C-MAPSS subsets.
# These are uninformative for modelling and are documented — not silently dropped.
LOW_VARIANCE_SENSORS = {"sensor_1", "sensor_5", "sensor_10", "sensor_16", "sensor_18", "sensor_19"}

PIPELINE_VERSION = "1.0.0"

# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class CMAPSSSubset:
    """Parsed, validated C-MAPSS sub-dataset (one of FD001–FD004)."""
    subset: str                     # "FD001" … "FD004"
    train: pd.DataFrame             # raw training rows (no RUL column)
    test: pd.DataFrame              # raw test rows (truncated trajectories)
    rul_test: pd.Series             # true RUL at last test cycle (indexed 0-based)
    # Derived immediately after parsing
    train_units: int = field(init=False)
    test_units: int = field(init=False)

    def __post_init__(self) -> None:
        self.train_units = int(self.train["unit_id"].nunique())
        self.test_units = int(self.test["unit_id"].nunique())

    def summary(self) -> dict:
        return {
            "subset": self.subset,
            "train_units": self.train_units,
            "test_units": self.test_units,
            "train_rows": len(self.train),
            "test_rows": len(self.test),
            "test_rul_values": len(self.rul_test),
            "train_cycle_range": [int(self.train["cycle"].min()), int(self.train["cycle"].max())],
            "sensors": SENSOR_COLS,
        }


@dataclass
class CMAPSSFeatures:
    """Processed features + labels split — ready for ML but NOT combined."""
    subset: str
    split: Literal["train", "test"]
    features: pd.DataFrame     # NO true_rul column
    labels: pd.DataFrame       # only true_rul column (same index as features)
    metadata: dict             # processing parameters


# ─── Parser ──────────────────────────────────────────────────────────────────

def parse_cmapss_file(path: Path) -> pd.DataFrame:
    """Read a raw C-MAPSS text file into a DataFrame with proper column names."""
    if not path.exists():
        raise FileNotFoundError(f"C-MAPSS raw file not found: {path}")

    df = pd.read_csv(path, sep=r"\s+", header=None, engine="python")

    # The official files have 26 columns; some mirrors add a trailing delimiter
    # which creates a 27th NaN column.  Drop it cleanly.
    if df.shape[1] == 27:
        df = df.iloc[:, :26]

    if df.shape[1] != 26:
        raise ValueError(
            f"Unexpected column count in {path.name}: expected 26, got {df.shape[1]}"
        )

    df.columns = CMAPSS_COLUMNS
    df = df.astype({col: "int32" for col in ["unit_id", "cycle"]})
    df = df.astype({col: "float32" for col in SETTING_COLS + SENSOR_COLS})

    # Validate no nulls
    null_counts = df.isnull().sum()
    if null_counts.any():
        bad = null_counts[null_counts > 0].to_dict()
        raise ValueError(f"Null values found in {path.name}: {bad}")

    return df


def parse_rul_file(path: Path) -> pd.Series:
    """Read an RUL_FDxxx.txt file into a Series (one value per test unit)."""
    if not path.exists():
        raise FileNotFoundError(f"C-MAPSS RUL file not found: {path}")
    values = pd.read_csv(path, header=None, squeeze=False).iloc[:, 0]
    return pd.Series(values.values, name="true_rul_at_cutoff", dtype="float32")


def load_cmapss_subset(raw_dir: Path, subset: str) -> CMAPSSSubset:
    """Parse all three files for one C-MAPSS subset (e.g. 'FD001').

    Parameters
    ----------
    raw_dir : Path
        Directory containing the raw .txt files.
    subset : str
        One of 'FD001', 'FD002', 'FD003', 'FD004'.

    Returns
    -------
    CMAPSSSubset with validated DataFrames.
    """
    subset = subset.upper()
    train = parse_cmapss_file(raw_dir / f"train_{subset}.txt")
    test  = parse_cmapss_file(raw_dir / f"test_{subset}.txt")
    rul   = parse_rul_file(raw_dir / f"RUL_{subset}.txt")

    # Validate RUL vector length matches test unit count
    n_test_units = int(test["unit_id"].nunique())
    if len(rul) != n_test_units:
        raise ValueError(
            f"{subset}: RUL vector length {len(rul)} != test unit count {n_test_units}"
        )

    log.info(
        "Loaded %s — train: %d units / %d rows | test: %d units / %d rows",
        subset, train["unit_id"].nunique(), len(train),
        test["unit_id"].nunique(), len(test),
    )
    return CMAPSSSubset(subset=subset, train=train, test=test, rul_test=rul)


# ─── RUL labelling ───────────────────────────────────────────────────────────

def compute_rul_labels(
    df: pd.DataFrame,
    rul_cap: int = 125,
) -> pd.Series:
    """Compute piecewise-linear RUL labels for training data.

    For each unit, RUL at cycle t = max_cycle - t.
    Clipped at *rul_cap* so that early healthy cycles don't dominate learning.

    IMPORTANT: the returned Series has the SAME index as *df*.
    It must be stored separately and must NEVER be added to the feature DataFrame.
    """
    max_cycles = df.groupby("unit_id")["cycle"].transform("max")
    raw_rul = (max_cycles - df["cycle"]).astype("float32")
    capped_rul = raw_rul.clip(upper=rul_cap)
    return pd.Series(capped_rul.values, index=df.index, name="true_rul", dtype="float32")


# ─── Feature engineering ──────────────────────────────────────────────────────

def add_rolling_features(
    df: pd.DataFrame,
    window: int = 15,
    sensor_cols: list[str] | None = None,
    drop_low_variance: bool = True,
) -> pd.DataFrame:
    """Add rolling-window statistics per unit trajectory.

    Features added per sensor (with suffix):
      _mean, _std, _min, _max, _range, _trend

    Parameters
    ----------
    window : int
        Rolling window in cycles. min_periods = 1 so early cycles are not NaN.
    sensor_cols : list[str] or None
        Sensors to compute rolling stats on. Defaults to all 21 minus low-variance.
    drop_low_variance : bool
        If True, low-variance sensors are excluded from rolling features.
        Their raw values are still retained.

    Notes
    -----
    - Features are computed PER UNIT so trajectory boundaries are respected.
    - The resulting DataFrame retains unit_id, cycle, settings, and all raw sensors
      plus the new rolling columns.
    """
    if sensor_cols is None:
        if drop_low_variance:
            sensor_cols = [s for s in SENSOR_COLS if s not in LOW_VARIANCE_SENSORS]
        else:
            sensor_cols = SENSOR_COLS

    out_parts = []

    for unit_id, group in df.groupby("unit_id", sort=False):
        g = group.copy().sort_values("cycle")
        for col in sensor_cols:
            rolled = g[col].rolling(window=window, min_periods=1)
            g[f"{col}_mean"]  = rolled.mean().astype("float32")
            g[f"{col}_std"]   = rolled.std(ddof=0).fillna(0).astype("float32")
            g[f"{col}_min"]   = rolled.min().astype("float32")
            g[f"{col}_max"]   = rolled.max().astype("float32")
            g[f"{col}_range"] = (g[f"{col}_max"] - g[f"{col}_min"]).astype("float32")
            # Linear trend slope over the window (robust to 1-point windows)
            g[f"{col}_trend"] = (
                g[col]
                .rolling(window=window, min_periods=2)
                .apply(lambda x: np.polyfit(np.arange(len(x)), x, 1)[0], raw=True)
                .fillna(0)
                .astype("float32")
            )
        out_parts.append(g)

    return pd.concat(out_parts, ignore_index=True)


def normalise_operating_conditions(df: pd.DataFrame) -> pd.DataFrame:
    """Add an operating-condition cluster label.

    FD002 and FD004 have 6 operating conditions identifiable by
    (setting_1, setting_2).  FD001 and FD003 have only 1 condition.

    A simple cluster is formed by rounding setting_1 to 1 d.p.
    and setting_2 to 2 d.p. — matching the official cluster definitions.
    """
    df = df.copy()
    df["op_condition"] = (
        df["setting_1"].round(1).astype(str)
        + "_"
        + df["setting_2"].round(2).astype(str)
    )
    return df


# ─── Full preprocessing pipeline ─────────────────────────────────────────────

def preprocess_cmapss(
    subset_data: CMAPSSSubset,
    *,
    rul_cap: int = 125,
    rolling_window: int = 15,
    drop_low_variance: bool = True,
) -> dict[str, CMAPSSFeatures]:
    """Full preprocessing pipeline for one C-MAPSS subset.

    Returns
    -------
    dict with keys 'train' and 'test', each a CMAPSSFeatures.

    Leakage guarantee
    -----------------
    - true_rul is computed and stored ONLY in CMAPSSFeatures.labels.
    - CMAPSSFeatures.features contains no true_rul column (verified by assertion).
    """
    params = {
        "rul_cap": rul_cap,
        "rolling_window": rolling_window,
        "drop_low_variance": drop_low_variance,
        "low_variance_sensors": sorted(LOW_VARIANCE_SENSORS),
        "pipeline_version": PIPELINE_VERSION,
    }

    results: dict[str, CMAPSSFeatures] = {}

    # ── TRAINING SPLIT ────────────────────────────────────────────────────────
    train_raw = subset_data.train.copy()
    train_rul = compute_rul_labels(train_raw, rul_cap=rul_cap)  # SEPARATE

    train_feat = add_rolling_features(
        normalise_operating_conditions(train_raw),
        window=rolling_window,
        drop_low_variance=drop_low_variance,
    )
    # Leakage guard: assert true_rul is NOT in the feature frame
    assert "true_rul" not in train_feat.columns, "LEAKAGE: true_rul in feature DataFrame"

    results["train"] = CMAPSSFeatures(
        subset=subset_data.subset,
        split="train",
        features=train_feat,
        labels=pd.DataFrame({"true_rul": train_rul.values}, index=train_feat.index),
        metadata=params,
    )

    # ── TEST SPLIT ────────────────────────────────────────────────────────────
    # For test data we know only the RUL at the LAST cycle of each truncated trajectory.
    # We assign NaN RUL to all but the last cycle (which gets the known value from rul_test).
    test_raw = subset_data.test.copy()
    test_feat = add_rolling_features(
        normalise_operating_conditions(test_raw),
        window=rolling_window,
        drop_low_variance=drop_low_variance,
    )

    # Build test labels: NaN for all cycles except the last of each unit
    last_cycles = test_feat.groupby("unit_id").apply(lambda g: g.index[-1])
    test_rul_values = np.full(len(test_feat), np.nan, dtype="float32")
    for unit_idx, (unit_id, last_idx) in enumerate(last_cycles.items()):
        test_rul_values[test_feat.index.get_loc(last_idx)] = subset_data.rul_test.iloc[unit_idx]

    assert "true_rul" not in test_feat.columns, "LEAKAGE: true_rul in feature DataFrame"

    results["test"] = CMAPSSFeatures(
        subset=subset_data.subset,
        split="test",
        features=test_feat,
        labels=pd.DataFrame({"true_rul": test_rul_values}, index=test_feat.index),
        metadata=params,
    )

    log.info(
        "%s preprocessed — train: %d rows / %d features | test: %d rows",
        subset_data.subset,
        len(results["train"].features),
        len(results["train"].features.columns),
        len(results["test"].features),
    )
    return results


# ─── Persistence ─────────────────────────────────────────────────────────────

def save_cmapss_features(
    processed: dict[str, CMAPSSFeatures],
    out_dir: Path,
) -> dict[str, Path]:
    """Save feature and label DataFrames as Parquet files.

    Output layout:
        <out_dir>/
          cmapss_{subset}_train_features.parquet
          cmapss_{subset}_train_labels.parquet
          cmapss_{subset}_test_features.parquet
          cmapss_{subset}_test_labels.parquet
          cmapss_{subset}_metadata.json

    Returns dict mapping logical name → output Path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    for split, cf in processed.items():
        stem = f"cmapss_{cf.subset.lower()}_{split}"

        feat_path = out_dir / f"{stem}_features.parquet"
        label_path = out_dir / f"{stem}_labels.parquet"

        cf.features.to_parquet(feat_path, index=False, compression="snappy")
        cf.labels.to_parquet(label_path, index=False, compression="snappy")

        paths[f"{split}_features"] = feat_path
        paths[f"{split}_labels"] = label_path
        log.info("  Saved %s (%d rows, %d cols)", feat_path.name, len(cf.features), len(cf.features.columns))
        log.info("  Saved %s (%d rows)", label_path.name, len(cf.labels))

    # Metadata
    meta_path = out_dir / f"cmapss_{processed['train'].subset.lower()}_metadata.json"
    meta = {
        "subset": processed["train"].subset,
        "parameters": processed["train"].metadata,
        "train_rows": len(processed["train"].features),
        "test_rows": len(processed["test"].features),
        "feature_columns": list(processed["train"].features.columns),
        "label_columns": ["true_rul"],
        "leakage_guard": "true_rul absent from features — verified by assertion",
    }
    with meta_path.open("w") as fh:
        json.dump(meta, fh, indent=2)
    paths["metadata"] = meta_path

    return paths
