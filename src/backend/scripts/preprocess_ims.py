#!/usr/bin/env python3
"""
Preprocess NASA IMS Bearing Vibration dataset.

Usage (from repo root):
    source .venv/bin/activate
    python src/backend/scripts/preprocess_ims.py [--runs run1,run2,run3]

Requires:
    src/backend/data/raw/ims/1st_test/   (run1 snapshot files)
    src/backend/data/raw/ims/2nd_test/   (run2)
    src/backend/data/raw/ims/3rd_test/   (run3)

See docs/DATA_PROVENANCE.md for download instructions (manual, ~600 MB).

Outputs (in src/backend/data/processed/ims/):
    ims_features.parquet       — extracted time + frequency domain features
    ims_labels.parquet         — failure labels (separated from features)
    ims_features.provenance.json

Processing note:
    Raw waveform files are NOT stored.
    Only extracted statistical / spectral features per bearing per snapshot are saved.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "backend"))

from app.ml.ingestion.ims import process_ims_dataset, save_ims_features
from app.ml.ingestion.provenance import write_provenance
from app.ml.validation.schema import validate_ims_features

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

RAW_IMS_DIR = REPO_ROOT / "src" / "backend" / "data" / "raw" / "ims"
OUT_DIR     = REPO_ROOT / "src" / "backend" / "data" / "processed" / "ims"


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess NASA IMS bearing dataset")
    parser.add_argument(
        "--runs",
        default="run1,run2,run3",
        help="Comma-separated run IDs to process (default: run1,run2,run3)",
    )
    parser.add_argument(
        "--max-snapshots",
        type=int,
        default=None,
        help="Process at most N snapshots per run (for quick validation)",
    )
    parser.add_argument(
        "--failure-fraction",
        type=float,
        default=0.05,
        help="Fraction of last snapshots to label as failure (default: 0.05)",
    )
    parser.add_argument(
        "--no-checksums",
        action="store_true",
        help="Skip SHA-256 provenance checksums (faster during dev)",
    )
    args = parser.parse_args()

    runs = [r.strip() for r in args.runs.split(",")]

    # Check at least one run directory exists
    available = [r for r in runs if (RAW_IMS_DIR / _run_dir(r)).exists()]
    if not available:
        log.error(
            "No IMS run directories found in %s\n"
            "Expected subdirectories: 1st_test, 2nd_test, 3rd_test\n"
            "See docs/DATA_PROVENANCE.md for manual download instructions.",
            RAW_IMS_DIR,
        )
        sys.exit(1)

    log.info("Processing IMS runs: %s", available)

    result = process_ims_dataset(
        raw_ims_dir=RAW_IMS_DIR,
        runs=available,
        max_snapshots_per_run=args.max_snapshots,
        failure_fraction=args.failure_fraction,
    )

    # Validate
    report = validate_ims_features(result.features, result.labels)
    log.info(report.summary())
    try:
        report.raise_if_failed()
    except ValueError as exc:
        log.error("Validation FAILED — aborting save\n%s", exc)
        sys.exit(1)

    # Save
    paths = save_ims_features(result, OUT_DIR)

    # Provenance
    source_paths = [
        RAW_IMS_DIR / _run_dir(r)
        for r in available
        if (RAW_IMS_DIR / _run_dir(r)).exists()
    ]
    notes = (
        "IMS bearing vibration features extracted by MissionReady AI pipeline. "
        "Raw waveforms (20480 Hz) are NOT stored. "
        "Only time-domain and frequency-domain statistical features are persisted. "
        "failure_label stored in labels file only — NOT in feature file (leakage guard). "
        f"Runs processed: {available}. "
        f"Failure fraction: {args.failure_fraction}."
    )
    write_provenance(
        dataset_id="ims_bearings",
        output_path=paths["features"],
        source_paths=source_paths,
        pipeline_version=result.parameters["pipeline_version"],
        parameters=result.parameters,
        notes=notes,
        compute_checksums=not args.no_checksums,
    )

    log.info("✓ IMS preprocessing complete — outputs in %s", OUT_DIR)


def _run_dir(run_id: str) -> str:
    from app.ml.ingestion.ims import RUN_DIR_MAP
    return RUN_DIR_MAP.get(run_id, run_id)


if __name__ == "__main__":
    main()
