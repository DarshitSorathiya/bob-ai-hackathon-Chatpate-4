"""
/api/v1/readiness — fleet readiness overview and per-asset evaluation trigger.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import CurrentUser, DbSession
from app.core.responses import make_response
from app.repositories.operations_repository import ReadinessRepository
from app.services.readiness_service import ReadinessService

router = APIRouter(prefix="/readiness", tags=["readiness"])

_readiness_repo = ReadinessRepository()
_readiness_svc = ReadinessService()


@router.get("", summary="Fleet-level readiness summary")
def fleet_readiness_summary(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
):
    """Return counts of READY / AT_RISK / NOT_READY / UNKNOWN across the fleet."""
    rid = request.headers.get("X-Request-ID", "")
    summary = _readiness_svc.get_fleet_summary(db)
    return make_response(summary, rid)


@router.post("/evaluate/{asset_id}", summary="Trigger readiness evaluation for an asset")
def evaluate_asset_readiness(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    asset_id: uuid.UUID,
    mission_id: uuid.UUID | None = None,
    mission_duration_hours: float = 0.0,
):
    """Run the deterministic ReadinessEngine for this asset and persist the result.

    This endpoint does NOT invoke an LLM. The result is derived solely from
    DB records (predictions, work orders, data quality events).
    """
    rid = request.headers.get("X-Request-ID", "")
    try:
        output = _readiness_svc.evaluate_asset(
            db,
            asset_id,
            mission_id=mission_id,
            mission_duration_hours=mission_duration_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return make_response({
        "asset_id": output.asset_id,
        "asset_code": output.asset_code,
        "status": output.status.value,
        "primary_reason": output.primary_reason.value,
        "confidence": output.confidence,
        "contributing_factors": [
            {
                "code": f.code.value,
                "message": f.message,
                "severity": f.severity,
                "evidence": f.evidence,
            }
            for f in output.contributing_factors
        ],
        "evaluated_at": output.evaluated_at.isoformat(),
        "mission_id": output.mission_id,
    }, rid)


@router.get("/all", summary="List all latest readiness records")
def list_all_readiness(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    status_filter: str | None = None,
):
    rid = request.headers.get("X-Request-ID", "")
    import json
    records = _readiness_repo.list(db, status=status_filter)
    result = []
    for rec in records:
        factors = json.loads(rec.factors_json) if rec.factors_json else []
        result.append({
            "asset_id": str(rec.asset_id),
            "status": rec.status,
            "primary_reason": rec.primary_reason,
            "confidence": rec.confidence,
            "contributing_factors": factors,
            "evaluated_at": rec.evaluated_at.isoformat() if rec.evaluated_at else None,
            "mission_id": str(rec.mission_id) if rec.mission_id else None,
        })
    return make_response(result, rid)
