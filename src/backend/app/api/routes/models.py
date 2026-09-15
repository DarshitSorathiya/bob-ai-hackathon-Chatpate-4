"""
/api/v1/models — ML model registry viewer.

Lists all registered model versions from the file-system registry.
Restricted to MAINTAINER and ADMIN roles.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from app.api.deps import CurrentUser, require_roles
from app.core.responses import make_response
from app.core.roles import ADMIN, MAINTAINER

router = APIRouter(prefix="/models", tags=["models"])

# Resolve model artifact directory relative to this file
_MODELS_DIR = Path(__file__).resolve().parents[3] / "data" / "models"


def _read_json_safe(path: Path) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _list_model_versions() -> list[dict]:
    """Scan data/models/ and return metadata for every registered model."""
    if not _MODELS_DIR.exists():
        return []
    versions = []
    for tag_dir in sorted(_MODELS_DIR.iterdir()):
        if not tag_dir.is_dir():
            continue
        metadata_path = tag_dir / "metadata.json"
        if not metadata_path.exists():
            continue
        meta = _read_json_safe(metadata_path)
        evaluation = _read_json_safe(tag_dir / "evaluation.json")
        leakage = _read_json_safe(tag_dir / "leakage_check.json")
        feature_importance = _read_json_safe(tag_dir / "feature_importance.json")

        versions.append({
            "tag": meta.get("tag", tag_dir.name),
            "version_id": meta.get("version_id"),
            "task": meta.get("task"),
            "algorithm": meta.get("algorithm"),
            "feature_count": len(meta.get("feature_names", [])),
            "feature_version": meta.get("feature_version"),
            "created_at": meta.get("created_at"),
            "leakage_status": leakage.get("status", "UNKNOWN"),
            "evaluation": evaluation,
            "feature_importance": feature_importance,
            "training_metadata": meta.get("training_metadata", {}),
        })
    return versions


@router.get("", summary="List all registered model versions")
def list_models(
    request: Request,
    _user: CurrentUser,
    _roles=Depends(require_roles(MAINTAINER, ADMIN)),
):
    """Return all registered ML model versions with evaluation metrics.

    Reads from the file-system model registry (data/models/).
    Restricted to MAINTAINER and ADMIN roles.
    """
    rid = request.headers.get("X-Request-ID", "")
    versions = _list_model_versions()
    return make_response(versions, rid)


@router.get("/{tag}", summary="Get model version by tag")
def get_model(
    request: Request,
    tag: str,
    _user: CurrentUser,
    _roles=Depends(require_roles(MAINTAINER, ADMIN)),
):
    rid = request.headers.get("X-Request-ID", "")
    tag_dir = _MODELS_DIR / tag
    if not tag_dir.exists() or not (tag_dir / "metadata.json").exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Model '{tag}' not found")

    meta = _read_json_safe(tag_dir / "metadata.json")
    evaluation = _read_json_safe(tag_dir / "evaluation.json")
    leakage = _read_json_safe(tag_dir / "leakage_check.json")
    feature_importance = _read_json_safe(tag_dir / "feature_importance.json")

    return make_response({
        "tag": meta.get("tag", tag),
        "version_id": meta.get("version_id"),
        "task": meta.get("task"),
        "algorithm": meta.get("algorithm"),
        "feature_names": meta.get("feature_names", []),
        "feature_count": len(meta.get("feature_names", [])),
        "feature_version": meta.get("feature_version"),
        "created_at": meta.get("created_at"),
        "leakage_status": leakage.get("status", "UNKNOWN"),
        "leakage_violations": leakage.get("violations", []),
        "evaluation": evaluation,
        "feature_importance": feature_importance,
        "training_metadata": meta.get("training_metadata", {}),
    }, rid)
