#!/usr/bin/env python3
"""
Download external behavioral-reference datasets for MissionReady AI.

Usage (from repo root):
    source .venv/bin/activate
    python src/backend/scripts/download_datasets.py [--dataset cmapss|ims|all]

What it downloads
-----------------
C-MAPSS  — six text files from the Kaggle mirror / NASA mirror.
           Stored in src/backend/data/raw/cmapss/.

IMS      — three run archives from the NASA PCoe mirror.
           Stored in src/backend/data/raw/ims/.
           NOTE: Each run archive is ~150–300 MB compressed.

The script:
  1. Checks whether each file already exists (skip-if-present by default).
  2. Verifies SHA-256 checksums where known.
  3. Writes a download.log in each raw sub-directory.
  4. Does NOT run any preprocessing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
import urllib.request
from pathlib import Path
from datetime import UTC, datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# Repository root
REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_CMAPSS = REPO_ROOT / "src" / "backend" / "data" / "raw" / "cmapss"
RAW_IMS    = REPO_ROOT / "src" / "backend" / "data" / "raw" / "ims"

# ─── Download manifests ───────────────────────────────────────────────────────
# sha256 values are listed where publicly known.
# Some mirrors may host slightly different encodings; treat checksum mismatch
# as a warning rather than a hard failure so the user can supply the file manually.

CMAPSS_FILES: list[dict] = [
    # Primary mirror: Kaggle dataset "behrad3d/nasa-cmaps" (public, no login required)
    # The NASA PCoe site requires a form submission; Kaggle provides identical files.
    # If Kaggle fails, user can download directly from:
    # https://data.nasa.gov/Aerospace/CMAPSS-Jet-Engine-Simulated-Data/ff5v-kuh6
    {
        "filename": "train_FD001.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/train_FD001.txt",
        "sha256": None,  # checksum verified at parse time via shape checks
    },
    {
        "filename": "test_FD001.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/test_FD001.txt",
        "sha256": None,
    },
    {
        "filename": "RUL_FD001.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/RUL_FD001.txt",
        "sha256": None,
    },
    {
        "filename": "train_FD002.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/train_FD002.txt",
        "sha256": None,
    },
    {
        "filename": "test_FD002.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/test_FD002.txt",
        "sha256": None,
    },
    {
        "filename": "RUL_FD002.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/RUL_FD002.txt",
        "sha256": None,
    },
    {
        "filename": "train_FD003.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/train_FD003.txt",
        "sha256": None,
    },
    {
        "filename": "test_FD003.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/test_FD003.txt",
        "sha256": None,
    },
    {
        "filename": "RUL_FD003.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/RUL_FD003.txt",
        "sha256": None,
    },
    {
        "filename": "train_FD004.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/train_FD004.txt",
        "sha256": None,
    },
    {
        "filename": "test_FD004.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/test_FD004.txt",
        "sha256": None,
    },
    {
        "filename": "RUL_FD004.txt",
        "url": "https://raw.githubusercontent.com/Samimust/predictive-maintenance/master/CMAPSSData/RUL_FD004.txt",
        "sha256": None,
    },
]

# IMS: NASA PCoe provides a zip per run.
# The archives are large (~150–300 MB each); only download if explicitly requested.
IMS_FILES: list[dict] = [
    {
        "filename": "IMS_bearing_run1.zip",
        "url": "https://ti.arc.nasa.gov/c/15/",
        "sha256": None,
        "note": "NASA PCoe — requires browser or direct curl. See docs/DATA_PROVENANCE.md for manual steps.",
        "manual_only": True,
    },
    {
        "filename": "IMS_bearing_run2.zip",
        "url": "https://ti.arc.nasa.gov/c/15/",
        "sha256": None,
        "manual_only": True,
    },
    {
        "filename": "IMS_bearing_run3.zip",
        "url": "https://ti.arc.nasa.gov/c/15/",
        "sha256": None,
        "manual_only": True,
    },
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest: Path, expected_sha256: str | None = None) -> bool:
    """Download *url* to *dest*. Returns True on success."""
    log.info("  Downloading %s → %s", url, dest.name)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as fh:
                shutil.copyfileobj(resp, fh)
    except Exception as exc:
        log.error("  FAILED: %s", exc)
        return False

    if expected_sha256:
        actual = sha256_file(dest)
        if actual != expected_sha256:
            log.warning("  Checksum mismatch! expected=%s actual=%s", expected_sha256, actual)
        else:
            log.info("  Checksum OK")

    log.info("  Saved %s (%.1f KB)", dest.name, dest.stat().st_size / 1024)
    return True


def write_download_log(directory: Path, entries: list[dict]) -> None:
    log_path = directory / "download.log"
    with log_path.open("w") as fh:
        json.dump(
            {"downloaded_at": datetime.now(UTC).isoformat(), "files": entries},
            fh,
            indent=2,
        )


# ─── Dataset downloaders ─────────────────────────────────────────────────────

def download_cmapss(force: bool = False) -> None:
    log.info("─── C-MAPSS ───────────────────────────────────────")
    RAW_CMAPSS.mkdir(parents=True, exist_ok=True)
    results = []

    for entry in CMAPSS_FILES:
        dest = RAW_CMAPSS / entry["filename"]
        if dest.exists() and not force:
            log.info("  SKIP (exists): %s", entry["filename"])
            results.append({"file": entry["filename"], "status": "skipped"})
            continue
        ok = download_file(entry["url"], dest, entry.get("sha256"))
        results.append({"file": entry["filename"], "status": "ok" if ok else "failed"})

    write_download_log(RAW_CMAPSS, results)
    ok_count = sum(1 for r in results if r["status"] in ("ok", "skipped"))
    log.info("C-MAPSS: %d/%d files ready", ok_count, len(CMAPSS_FILES))


def download_ims(force: bool = False) -> None:
    log.info("─── IMS Bearings ──────────────────────────────────")
    RAW_IMS.mkdir(parents=True, exist_ok=True)

    for entry in IMS_FILES:
        if entry.get("manual_only"):
            log.warning(
                "  MANUAL REQUIRED: %s\n"
                "  The NASA PCoe IMS dataset requires a form submission at:\n"
                "  https://ti.arc.nasa.gov/tech/dash/groups/pcoe/prognostic-data-repository/\n"
                "  Download the three run zips and unzip into: %s",
                entry["filename"],
                RAW_IMS,
            )

    log.info(
        "\nIMS manual instructions:\n"
        "  1. Visit https://ti.arc.nasa.gov/tech/dash/groups/pcoe/prognostic-data-repository/\n"
        "  2. Download '1st_test.zip', '2nd_test.zip', '3rd_test.zip'\n"
        "  3. Unzip each into src/backend/data/raw/ims/ maintaining the run subdirectory:\n"
        "       data/raw/ims/1st_test/   (984 files, ~10 ms each)\n"
        "       data/raw/ims/2nd_test/   (984 files)\n"
        "       data/raw/ims/3rd_test/   (6324 files)\n"
        "  4. Run: python scripts/preprocess_ims.py\n"
    )


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Download MissionReady AI reference datasets")
    parser.add_argument(
        "--dataset",
        choices=["cmapss", "ims", "all"],
        default="cmapss",
        help="Which dataset to download (default: cmapss). IMS requires manual steps.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the file already exists.",
    )
    args = parser.parse_args()

    if args.dataset in ("cmapss", "all"):
        download_cmapss(force=args.force)

    if args.dataset in ("ims", "all"):
        download_ims(force=args.force)


if __name__ == "__main__":
    main()
