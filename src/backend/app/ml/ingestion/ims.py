"""
NASA IMS Bearing Vibration Dataset — Feature Extraction Pipeline.

Dataset contract
----------------
The IMS dataset contains three run-to-failure bearing experiments.
Each run directory contains one file per 10-minute snapshot.
Each file has 4 columns (one per bearing channel), each with 20480 rows
of raw acceleration waveform at 20480 Hz (1-second snapshot).

Processing philosophy
---------------------
Raw waveforms are NOT loaded into the application database.
Only extracted statistical and spectral features per bearing per snapshot
are persisted.  This keeps the processed dataset manageable (~MB vs ~GB).

Feature set extracted per bearing per snapshot
-----------------------------------------------
Time domain:
  mean           — arithmetic mean of the waveform
  std            — standard deviation
  rms            — root mean square (energy indicator)
  peak           — maximum absolute value
  peak_to_peak   — max - min
  skewness       — third standardised moment (impulsive events)
  kurtosis       — fourth standardised moment (fault indicator)
  crest_factor   — peak / rms  (impulsiveness relative to RMS)
  impulse_factor — peak / mean(|x|)
  shape_factor   — rms / mean(|x|)

Frequency domain (via real FFT):
  dominant_freq  — frequency with maximum spectral magnitude (Hz)
  spectral_energy— sum of squared magnitudes
  spectral_centroid — power-weighted mean frequency (Hz)
  band_energy_0  — energy in 0–2000 Hz band
  band_energy_1  — energy in 2000–5000 Hz band
  band_energy_2  — energy in 5000–10240 Hz band
  spectral_entropy — Shannon entropy of normalised power spectrum

Additional:
  snapshot_index — ordinal snapshot number (0-based) within the run
  timestamp      — datetime parsed from filename (where possible)
  bearing_id     — channel index (0–3 for 4 bearings)
  run_id         — run identifier ("run1", "run2", "run3")
  failure_label  — 1 at failure snapshots, 0 otherwise (documented, NOT used as feature)

Failure labels (from published literature)
------------------------------------------
Run 1: Bearing 3 (channel 2) failed at end.
Run 2: Bearing 1 (channel 0) failed at end.
Run 3: Bearing 3 (channel 2) failed at end.
These are used ONLY to label ground-truth failure windows; they are stored in
a separate labels Parquet and must NOT be used as features.

References
----------
Hai Qiu, Jay Lee, Jing Lin, Gang Yu (2006). "Wavelet Filter-based Weak Signature
Detection Method and its Application on Roller Bearing Prognostics".
Journal of Sound and Vibration, 289(4), 1066-1090.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd
from scipy import stats
from scipy.fft import rfft, rfftfreq

log = logging.getLogger(__name__)

PIPELINE_VERSION = "1.0.0"
SAMPLING_RATE_HZ = 20480
N_BEARINGS = 4

# IMS run directory names as distributed by NASA PCoe
RUN_DIR_MAP = {
    "run1": "1st_test",
    "run2": "2nd_test",
    "run3": "3rd_test",
}

# Known failure bearings (channel index, 0-based) from published literature
FAILURE_BEARING: dict[str, int] = {
    "run1": 2,   # bearing 3
    "run2": 0,   # bearing 1
    "run3": 2,   # bearing 3
}

# Frequency bands (Hz) for band energy features
FREQUENCY_BANDS = [
    (0, 2000),
    (2000, 5000),
    (5000, SAMPLING_RATE_HZ // 2),
]


# ─── Time-domain features ─────────────────────────────────────────────────────

def _timedomain_features(signal: np.ndarray) -> dict[str, float]:
    """Extract time-domain statistical features from a 1-D signal."""
    n = len(signal)
    if n == 0:
        return {}

    abs_sig = np.abs(signal)
    rms = float(np.sqrt(np.mean(signal ** 2)))
    peak = float(np.max(abs_sig))
    mean_abs = float(np.mean(abs_sig))

    return {
        "mean":          float(np.mean(signal)),
        "std":           float(np.std(signal, ddof=0)),
        "rms":           rms,
        "peak":          peak,
        "peak_to_peak":  float(np.max(signal) - np.min(signal)),
        "skewness":      float(stats.skew(signal)),
        "kurtosis":      float(stats.kurtosis(signal, fisher=True)),  # excess kurtosis
        "crest_factor":  float(peak / rms) if rms > 0 else 0.0,
        "impulse_factor":float(peak / mean_abs) if mean_abs > 0 else 0.0,
        "shape_factor":  float(rms / mean_abs) if mean_abs > 0 else 0.0,
    }


# ─── Frequency-domain features ───────────────────────────────────────────────

def _freqdomain_features(
    signal: np.ndarray,
    fs: int = SAMPLING_RATE_HZ,
) -> dict[str, float]:
    """Extract frequency-domain features from a 1-D signal using real FFT."""
    n = len(signal)
    if n == 0:
        return {}

    spectrum = rfft(signal)
    magnitudes = np.abs(spectrum)
    freqs = rfftfreq(n, d=1.0 / fs)

    # Normalised power spectrum (probability-like, for entropy)
    power = magnitudes ** 2
    total_power = float(np.sum(power))
    if total_power > 0:
        prob = power / total_power
    else:
        prob = np.ones_like(power) / len(power)

    # Dominant frequency
    dominant_idx = int(np.argmax(magnitudes))
    dominant_freq = float(freqs[dominant_idx])

    # Spectral centroid
    if total_power > 0:
        centroid = float(np.sum(freqs * power) / total_power)
    else:
        centroid = 0.0

    # Shannon spectral entropy (nats)
    entropy = float(stats.entropy(prob + 1e-12))

    features: dict[str, float] = {
        "dominant_freq":     dominant_freq,
        "spectral_energy":   total_power,
        "spectral_centroid": centroid,
        "spectral_entropy":  entropy,
    }

    # Band energies
    for band_idx, (f_low, f_high) in enumerate(FREQUENCY_BANDS):
        mask = (freqs >= f_low) & (freqs < f_high)
        features[f"band_energy_{band_idx}"] = float(np.sum(power[mask]))

    return features


# ─── Single-snapshot feature extraction ──────────────────────────────────────

def extract_snapshot_features(
    snapshot_data: np.ndarray,
    bearing_idx: int,
    run_id: str,
    snapshot_index: int,
    timestamp: datetime | None,
    fs: int = SAMPLING_RATE_HZ,
) -> dict[str, object]:
    """Extract all features for one bearing channel of one snapshot file.

    Parameters
    ----------
    snapshot_data : np.ndarray, shape (N,)
        Raw acceleration waveform for a single bearing channel.
    bearing_idx : int
        0-based channel index (0–3).
    run_id : str
        "run1", "run2", or "run3".
    snapshot_index : int
        Ordinal position of this file within the run (0-based, chronological).
    timestamp : datetime or None
        Parsed from filename if available.
    fs : int
        Sampling frequency in Hz.
    """
    features: dict[str, object] = {
        "run_id":         run_id,
        "bearing_id":     bearing_idx,
        "snapshot_index": snapshot_index,
        "timestamp":      timestamp.isoformat() if timestamp else None,
    }
    features.update(_timedomain_features(snapshot_data))
    features.update(_freqdomain_features(snapshot_data, fs=fs))
    return features


# ─── Snapshot file loader ─────────────────────────────────────────────────────

def _parse_timestamp_from_filename(stem: str) -> datetime | None:
    """Attempt to parse datetime from IMS filename (format: yyyy.mm.dd.HH.MM.SS)."""
    pattern = r"(\d{4})\.(\d{2})\.(\d{2})\.(\d{2})\.(\d{2})\.(\d{2})"
    match = re.search(pattern, stem)
    if match:
        year, month, day, hour, minute, second = (int(x) for x in match.groups())
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass
    return None


def load_ims_snapshot(filepath: Path) -> np.ndarray | None:
    """Load one IMS snapshot file → array of shape (20480, 4).

    Returns None on parse failure so the pipeline can continue.
    """
    try:
        # IMS files are space-separated, no header
        data = pd.read_csv(filepath, sep=r"\s+", header=None).values.astype("float32")
        if data.shape[1] < N_BEARINGS:
            log.warning("Unexpected columns in %s: %s", filepath.name, data.shape)
            return None
        return data[:, :N_BEARINGS]  # keep exactly 4 channels
    except Exception as exc:
        log.warning("Failed to parse %s: %s", filepath.name, exc)
        return None


# ─── Run-level processing ─────────────────────────────────────────────────────

def _get_snapshot_files(run_dir: Path) -> list[Path]:
    """Return all snapshot files in a run directory, sorted chronologically."""
    # IMS files are named by timestamp or sequentially; sort lexicographically
    # (timestamp-named files sort chronologically).
    files = sorted(
        [f for f in run_dir.iterdir() if f.is_file() and not f.name.startswith(".")],
    )
    return files


def process_ims_run(
    run_dir: Path,
    run_id: str,
    max_snapshots: int | None = None,
) -> Iterator[dict[str, object]]:
    """Yield one feature dict per (snapshot, bearing) for a run.

    Parameters
    ----------
    run_dir : Path
        Directory containing snapshot files for this run.
    run_id : str
        "run1", "run2", or "run3".
    max_snapshots : int or None
        If set, process at most this many snapshots (useful for testing).
    """
    files = _get_snapshot_files(run_dir)
    if max_snapshots is not None:
        files = files[:max_snapshots]

    total = len(files)
    log.info("Processing %s: %d snapshot files", run_id, total)

    for snapshot_idx, filepath in enumerate(files):
        if snapshot_idx % 200 == 0:
            log.info("  %s: %d / %d snapshots processed", run_id, snapshot_idx, total)

        data = load_ims_snapshot(filepath)
        if data is None:
            continue

        ts = _parse_timestamp_from_filename(filepath.stem)

        for bearing_idx in range(N_BEARINGS):
            signal = data[:, bearing_idx]
            yield extract_snapshot_features(
                snapshot_data=signal,
                bearing_idx=bearing_idx,
                run_id=run_id,
                snapshot_index=snapshot_idx,
                timestamp=ts,
            )


# ─── Failure label generation ─────────────────────────────────────────────────

def generate_failure_labels(
    features_df: pd.DataFrame,
    failure_fraction: float = 0.05,
) -> pd.DataFrame:
    """Generate conservative failure labels for IMS runs.

    Labels the last *failure_fraction* of snapshots for the known-failure bearing
    as failure=1.  All other (run, bearing) combinations are labelled 0.

    IMPORTANT: These labels are stored in a SEPARATE DataFrame and must NEVER
    be included in the feature DataFrame used for model training.
    """
    labels = pd.DataFrame(index=features_df.index)
    labels["failure_label"] = 0

    for run_id, failed_bearing_idx in FAILURE_BEARING.items():
        mask_run = features_df["run_id"] == run_id
        mask_bearing = features_df["bearing_id"] == failed_bearing_idx
        mask = mask_run & mask_bearing
        if not mask.any():
            continue

        run_snapshots = features_df.loc[mask, "snapshot_index"].values
        max_snapshot = int(run_snapshots.max())
        failure_threshold = int(max_snapshot * (1 - failure_fraction))
        failure_mask = mask & (features_df["snapshot_index"] >= failure_threshold)
        labels.loc[failure_mask, "failure_label"] = 1

    log.info(
        "IMS failure labels: %d failure windows / %d total",
        int(labels["failure_label"].sum()),
        len(labels),
    )
    return labels


# ─── Full pipeline ────────────────────────────────────────────────────────────

@dataclass
class IMSFeatures:
    """Processed IMS features + labels — kept strictly separate."""
    features: pd.DataFrame   # NO failure_label column
    labels: pd.DataFrame     # only failure_label
    runs_processed: list[str]
    total_snapshots: int
    parameters: dict


def process_ims_dataset(
    raw_ims_dir: Path,
    *,
    runs: list[str] | None = None,
    max_snapshots_per_run: int | None = None,
    failure_fraction: float = 0.05,
) -> IMSFeatures:
    """Process one or more IMS runs into a single feature DataFrame.

    Parameters
    ----------
    raw_ims_dir : Path
        Root of data/raw/ims/ (must contain the run subdirectories).
    runs : list[str] or None
        Subset of ["run1","run2","run3"] to process. None = all.
    max_snapshots_per_run : int or None
        Cap for testing / partial runs.
    failure_fraction : float
        Proportion of last snapshots to label as failure.

    Returns
    -------
    IMSFeatures with features and labels separated.
    """
    if runs is None:
        runs = list(RUN_DIR_MAP.keys())

    all_rows: list[dict] = []
    processed_runs: list[str] = []

    for run_id in runs:
        run_dir = raw_ims_dir / RUN_DIR_MAP[run_id]
        if not run_dir.exists():
            log.warning("IMS run directory missing: %s — skipping %s", run_dir, run_id)
            continue
        for row in process_ims_run(run_dir, run_id, max_snapshots=max_snapshots_per_run):
            all_rows.append(row)
        processed_runs.append(run_id)

    if not all_rows:
        raise RuntimeError(
            "No IMS data processed. Check that raw data is present in:\n"
            f"  {raw_ims_dir}\n"
            "Run: python scripts/download_datasets.py --dataset ims"
        )

    features_df = pd.DataFrame(all_rows).reset_index(drop=True)

    # Ensure numeric columns are float32 (metadata cols remain object/str)
    numeric_cols = [
        c for c in features_df.columns
        if c not in ("run_id", "timestamp")
    ]
    features_df[numeric_cols] = features_df[numeric_cols].astype("float32")

    # Generate labels BEFORE asserting no failure_label in features
    labels_df = generate_failure_labels(features_df, failure_fraction=failure_fraction)

    # Leakage guard
    assert "failure_label" not in features_df.columns, "LEAKAGE: failure_label in features"

    params = {
        "pipeline_version": PIPELINE_VERSION,
        "sampling_rate_hz": SAMPLING_RATE_HZ,
        "frequency_bands": FREQUENCY_BANDS,
        "failure_fraction": failure_fraction,
        "runs_processed": processed_runs,
        "max_snapshots_per_run": max_snapshots_per_run,
        "n_bearings": N_BEARINGS,
    }

    log.info(
        "IMS processing complete: %d rows / %d feature columns / %d runs",
        len(features_df),
        len(features_df.columns),
        len(processed_runs),
    )

    return IMSFeatures(
        features=features_df,
        labels=labels_df,
        runs_processed=processed_runs,
        total_snapshots=len(all_rows) // N_BEARINGS,
        parameters=params,
    )


def save_ims_features(result: IMSFeatures, out_dir: Path) -> dict[str, Path]:
    """Save IMS feature and label Parquet files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    feat_path = out_dir / "ims_features.parquet"
    label_path = out_dir / "ims_labels.parquet"

    result.features.to_parquet(feat_path, index=False, compression="snappy")
    result.labels.to_parquet(label_path, index=False, compression="snappy")

    paths["features"] = feat_path
    paths["labels"] = label_path

    log.info("Saved %s (%d rows, %d cols)", feat_path.name, len(result.features), len(result.features.columns))
    log.info("Saved %s (%d rows)", label_path.name, len(result.labels))

    return paths
