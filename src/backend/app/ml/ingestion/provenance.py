"""
Provenance tracking for MissionReady AI data pipeline.

Every processed output file is accompanied by a sidecar ``<stem>.provenance.json``
that records what it is, where its source data came from, how it was produced,
and when — enabling full reproducibility audits.

Design rule: provenance is written *after* the output is successfully produced.
If writing fails, the output file is not trustworthy.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Provenance schema version — bump when the structure changes
PROVENANCE_SCHEMA_VERSION = "1.0.0"

# Path to the dataset registry relative to this file's package root
_REGISTRY_PATH = Path(__file__).resolve().parents[3] / "data" / "dataset_registry.json"


# ─── Data classes ────────────────────────────────────────────────────────────

@dataclass
class SourceFile:
    path: str
    sha256: str | None


@dataclass
class ProvenanceRecord:
    schema_version: str
    dataset_id: str
    dataset_name: str
    output_file: str
    output_sha256: str | None
    created_at: str
    pipeline_version: str
    python_version: str
    platform: str
    source_files: list[SourceFile]
    parameters: dict[str, Any]
    notes: str = ""
    warnings: list[str] = field(default_factory=list)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Compute SHA-256 hex digest of a file without loading it fully into RAM."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _load_registry() -> dict[str, Any]:
    if not _REGISTRY_PATH.exists():
        return {}
    with _REGISTRY_PATH.open() as fh:
        registry = json.load(fh)
    return {ds["id"]: ds for ds in registry.get("datasets", [])}


# ─── Public API ───────────────────────────────────────────────────────────────

def write_provenance(
    *,
    dataset_id: str,
    output_path: Path,
    source_paths: list[Path],
    pipeline_version: str,
    parameters: dict[str, Any],
    notes: str = "",
    warnings: list[str] | None = None,
    compute_checksums: bool = True,
) -> Path:
    """Write a ``.provenance.json`` sidecar next to *output_path*.

    Parameters
    ----------
    dataset_id:
        Must match an ``id`` in ``dataset_registry.json``.
    output_path:
        The processed file just produced (Parquet, CSV, …).
    source_paths:
        Raw input files consumed.
    pipeline_version:
        A short string identifying the preprocessing code version (e.g. "1.0.0").
    parameters:
        Key/value pairs of every configurable preprocessing parameter used
        (window size, RUL cap, etc.).  All values must be JSON-serialisable.
    notes:
        Free-text remarks (dataset interpretation notes, caveats, …).
    warnings:
        Non-fatal issues encountered during processing.
    compute_checksums:
        If False, skip SHA-256 computation (faster for large files during dev).

    Returns
    -------
    Path
        Path to the written provenance sidecar.
    """
    registry = _load_registry()
    dataset_meta = registry.get(dataset_id, {})
    dataset_name = dataset_meta.get("name", dataset_id)

    source_files = []
    for p in source_paths:
        checksum = sha256_file(p) if compute_checksums and p.exists() else None
        source_files.append(SourceFile(path=str(p), sha256=checksum))

    output_sha256 = None
    if compute_checksums and output_path.exists():
        output_sha256 = sha256_file(output_path)

    record = ProvenanceRecord(
        schema_version=PROVENANCE_SCHEMA_VERSION,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        output_file=str(output_path),
        output_sha256=output_sha256,
        created_at=datetime.now(UTC).isoformat(),
        pipeline_version=pipeline_version,
        python_version=sys.version,
        platform=platform.platform(),
        source_files=source_files,
        parameters=parameters,
        notes=notes,
        warnings=warnings or [],
    )

    provenance_path = output_path.with_suffix("").with_suffix(".provenance.json")
    # If the output is already .provenance.json, avoid a collision
    if output_path.suffix == ".json" and output_path.stem.endswith(".provenance"):
        raise ValueError("output_path must not itself be a provenance file")

    with provenance_path.open("w") as fh:
        json.dump(asdict(record), fh, indent=2)

    return provenance_path


def load_provenance(output_path: Path) -> dict[str, Any] | None:
    """Load the provenance sidecar for *output_path*, or None if absent."""
    provenance_path = output_path.with_suffix("").with_suffix(".provenance.json")
    if not provenance_path.exists():
        return None
    with provenance_path.open() as fh:
        return json.load(fh)
