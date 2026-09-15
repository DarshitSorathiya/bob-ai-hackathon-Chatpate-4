#!/usr/bin/env python3
"""
Preprocess NASA C-MAPSS dataset — all four subsets (FD001–FD004).

Usage (from repo root):
    source .venv/bin/activate
    python src/backend/scripts/preprocess_cmapss.py [--subset FD001] [--no-checksums]

Requires:
    src/backend/data/raw/cmapss/train_FD001.txt (etc.) — run download_datasets.py first.

Outputs (in src/backend/data/processed/cmapss/):
    cmapss_fd001_train_features.parquet
    cmapss_fd001_train_labels.parquet
    cmapss_fd001_test_features.parquet
    cmapss_fd001_test_labels.parquet
    cmapss_fd001_metadata.json
    cmapss_fd001_train_features.provenance.json
    ... (one provenance sidecar per output)
    + same pattern for FD002, FD003, FD004
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure src/backend is on the path when run as a script
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "backend"))

from app.ml.ingestion.cmapss import (
    load_cmapss_subset,
    preprocess_cmapss,
    save_cmapss_features,
)
from app.ml.ingestion.provenance import write_provenance
from app.ml.validation.schema import validate_cmapss_features

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

RAW_DIR  = REPO_ROOT / "src" / "backend" / "data" / "raw" / "cmapss"
OUT_DIR  = REPO_ROOT / "src" / "backend" / "data" / "processed" / "cmapss"

ALL_SUBSETS = ["FD001", "FD002", "FD003", "FD004"]

# Expected minimum unit counts per subset per split (for validation)
EXPECTED_UNITS: dict[str, dict[str, int]] = {
    "FD001": {"train": 100, "test": 100},
    "FD002": {"train": 260, "test": 259},
    "FD003": {"train": 100, "test": 100},
    "FD004": {"train": 248, "test": 249},
}


def process_subset(
    subset: str,
    rul_cap: int = 125,
    rolling_window: int = 15,
    compute_checksums: bool = True,
) -> bool:
    log.info("══════════════ %s ══════════════", subset)

    # 1. Parse
    try:
        raw = load_cmapss_subset(RAW_DIR, subset)
    except FileNotFoundError as exc:
        log.error("Raw files missing for %s: %s", subset, exc)
        log.error("Run: python src/backend/scripts/download_datasets.py --dataset cmapss")
        return False

    # 2. Preprocess
    processed = preprocess_cmapss(
        raw,
        rul_cap=rul_cap,
        rolling_window=rolling_window,
    )

    # 3. Validate before saving
    for split, cf in processed.items():
        expected_min = EXPECTED_UNITS.get(subset, {}).get(split, 1)
        report = validate_cmapss_features(
            cf.features,
            cf.labels,
            split=split,
            subset=subset,
            expected_min_units=expected_min,
        )
        log.info(report.summary())
        try:
            report.raise_if_failed()
        except ValueError as exc:
            log.error("Validation FAILED — aborting save for %s/%s\n%s", subset, split, exc)
            return False

    # 4. Save
    paths = save_cmapss_features(processed, OUT_DIR)

    # 5. Write provenance sidecars
    dataset_id = f"cmapss_{subset.lower()}"
    raw_source_paths = [
        RAW_DIR / f"train_{subset}.txt",
        RAW_DIR / f"test_{subset}.txt",
        RAW_DIR / f"RUL_{subset}.txt",
    ]
    params = processed["train"].metadata
    notes = (
        f"C-MAPSS {subset} preprocessed by MissionReady AI pipeline v{params['pipeline_version']}. "
        f"Piecewise-linear RUL cap: {rul_cap}. Rolling window: {rolling_window} cycles. "
        f"Low-variance sensors excluded from rolling features: {params.get('low_variance_sensors', [])}. "
        "true_rul stored in labels file only — NOT in feature file (leakage guard)."
    )

    for logical_name, out_path in paths.items():
        if logical_name == "metadata":
            continue
        write_provenance(
            dataset_id=dataset_id,
            output_path=out_path,
            source_paths=raw_source_paths,
            pipeline_version=params["pipeline_version"],
            parameters={**params, "output_type": logical_name},
            notes=notes,
            compute_checksums=compute_checksums,
        )

    log.info("✓ %s complete — outputs in %s", subset, OUT_DIR)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess NASA C-MAPSS dataset")
    parser.add_argument(
        "--subset",
        choices=ALL_SUBSETS + ["all"],
        default="all",
        help="Which subset to process (default: all)",
    )
    parser.add_argument(
        "--rul-cap",
        type=int,
        default=125,
        help="Piecewise-linear RUL cap in cycles (default: 125)",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=15,
        help="Rolling window size in cycles (default: 15)",
    )
    parser.add_argument(
        "--no-checksums",
        action="store_true",
        help="Skip SHA-256 computation for provenance (faster during dev)",
    )
    args = parser.parse_args()

    subsets = ALL_SUBSETS if args.subset == "all" else [args.subset]
    failures = []

    for subset in subsets:
        ok = process_subset(
            subset,
            rul_cap=args.rul_cap,
            rolling_window=args.window,
            compute_checksums=not args.no_checksums,
        )
        if not ok:
            failures.append(subset)

    if failures:
        log.error("Failed subsets: %s", failures)
        sys.exit(1)

    log.info("All C-MAPSS subsets processed successfully.")


if __name__ == "__main__":
    main()
