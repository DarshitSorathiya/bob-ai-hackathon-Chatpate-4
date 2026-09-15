"""
Model versioning and artifact registry.

Every trained model is assigned a version UUID and a version tag
(e.g. "rul-v1", "failure-24h-v1", "anomaly-v1").

Persisted artifacts
-------------------
  models/<version_id>/
      model.joblib          — serialised estimator
      metadata.json         — training metadata (hyperparams, seed, feature list)
      evaluation.json       — evaluation metrics
      feature_importance.json — feature importance / SHAP surrogate (where available)
      leakage_check.json    — leakage test result (must be PASS)

Usage
-----
registry = ModelRegistry(base_dir="data/models")
record = registry.register(
    task="rul",
    tag="rul-v1",
    estimator=fitted_model,
    feature_names=...,
    training_metadata=...,
    evaluation_metadata=...,
    leakage_result=...,
)
# Later:
record2 = registry.load("rul-v1")
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


@dataclass
class ModelRecord:
    """Metadata for one registered model version."""

    version_id: str
    task: str                        # "rul" | "failure" | "anomaly"
    tag: str                         # human-readable slug, e.g. "rul-xgb-v1"
    algorithm: str                   # e.g. "XGBRegressor"
    feature_names: list[str]
    feature_version: str             # hash of sorted feature names
    training_metadata: dict[str, Any]
    evaluation_metadata: dict[str, Any]
    leakage_result: dict[str, Any]   # {"status": "PASS"|"FAIL", "violations": [...]}
    created_at: str
    artifact_dir: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelRegistry:
    """File-system backed model artifact registry.

    Parameters
    ----------
    base_dir:
        Root directory for storing model artifacts.
        Default: <repo>/src/backend/data/models
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir is None:
            base_dir = (
                Path(__file__).resolve().parents[3] / "data" / "models"
            )
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ─── Write ────────────────────────────────────────────────────────────────

    def register(
        self,
        task: str,
        tag: str,
        estimator: object,
        feature_names: list[str],
        training_metadata: dict[str, Any],
        evaluation_metadata: dict[str, Any],
        leakage_result: dict[str, Any],
        feature_importance: dict[str, float] | None = None,
    ) -> ModelRecord:
        """Persist *estimator* and all metadata; return a ModelRecord.

        Raises ValueError if leakage_result["status"] != "PASS".
        """
        if leakage_result.get("status") != "PASS":
            raise ValueError(
                f"Cannot register model '{tag}': leakage check did not PASS. "
                f"Violations: {leakage_result.get('violations', [])}"
            )

        version_id = str(uuid.uuid4())
        artifact_dir = self.base_dir / tag
        artifact_dir.mkdir(parents=True, exist_ok=True)

        created_at = datetime.now(timezone.utc).isoformat()
        algorithm = type(estimator).__name__
        feature_version = _feature_hash(feature_names)

        record = ModelRecord(
            version_id=version_id,
            task=task,
            tag=tag,
            algorithm=algorithm,
            feature_names=sorted(feature_names),
            feature_version=feature_version,
            training_metadata=training_metadata,
            evaluation_metadata=evaluation_metadata,
            leakage_result=leakage_result,
            created_at=created_at,
            artifact_dir=str(artifact_dir),
        )

        # Persist artifacts
        joblib.dump(estimator, artifact_dir / "model.joblib")
        _write_json(record.to_dict(), artifact_dir / "metadata.json")
        _write_json(evaluation_metadata, artifact_dir / "evaluation.json")
        _write_json(leakage_result, artifact_dir / "leakage_check.json")
        if feature_importance is not None:
            _write_json(feature_importance, artifact_dir / "feature_importance.json")

        return record

    # ─── Read ─────────────────────────────────────────────────────────────────

    def load(self, tag: str) -> tuple[object, ModelRecord]:
        """Load model and metadata by tag.

        Returns
        -------
        (estimator, ModelRecord)
        """
        artifact_dir = self.base_dir / tag
        if not artifact_dir.exists():
            raise FileNotFoundError(
                f"No model registered with tag '{tag}' in {self.base_dir}"
            )
        estimator = joblib.load(artifact_dir / "model.joblib")
        meta = _read_json(artifact_dir / "metadata.json")
        record = ModelRecord(**meta)
        return estimator, record

    def list_tags(self) -> list[str]:
        """Return all registered model tags."""
        return sorted(
            d.name for d in self.base_dir.iterdir() if d.is_dir()
        )

    def exists(self, tag: str) -> bool:
        return (self.base_dir / tag / "model.joblib").exists()


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _feature_hash(feature_names: list[str]) -> str:
    """Short hash of the sorted feature list for version tracking."""
    import hashlib
    key = ",".join(sorted(feature_names))
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def _write_json(obj: dict | list, path: Path) -> None:
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def _read_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)
