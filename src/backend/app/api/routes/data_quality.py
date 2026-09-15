"""
/api/v1/data-quality — data quality events.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, DbSession
from app.core.responses import make_response
from app.repositories.operations_repository import DataQualityRepository
from app.repositories.fleet_repository import AssetRepository, SensorRepository
from app.schemas.operations import DataQualityEventResponse

router = APIRouter(prefix="/data-quality", tags=["data-quality"])

_dq_repo = DataQualityRepository()
_asset_repo = AssetRepository()
_sensor_repo = SensorRepository()


def _enrich(evt, db: DbSession) -> dict:
    """Add asset_code and sensor_code to a raw DataQualityEvent dict."""
    data = DataQualityEventResponse.model_validate(evt).model_dump()
    # alias detected_at → created_at for frontend consistency
    data["created_at"] = data.get("detected_at")
    data["issue_type"] = evt.event_type
    # Resolve asset_code
    if evt.asset_id:
        asset = _asset_repo.get(db, evt.asset_id)
        data["asset_code"] = asset.asset_code if asset else None
    else:
        data["asset_code"] = None
    # Resolve sensor_code
    if evt.sensor_id:
        sensor = _sensor_repo.get(db, evt.sensor_id)
        data["sensor_code"] = sensor.sensor_code if sensor else None
    else:
        data["sensor_code"] = None
    return data


@router.get("", summary="List data quality events")
def list_dq_events(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    asset_id: uuid.UUID | None = None,
    severity: str | None = None,
    issue_type: str | None = None,
    is_resolved: bool | None = None,
    skip: int = 0,
    limit: int = 100,
):
    rid = request.headers.get("X-Request-ID", "")
    events = _dq_repo.list(
        db,
        asset_id=asset_id,
        severity=severity,
        event_type=issue_type,
        is_resolved=is_resolved,
        skip=skip,
        limit=limit,
    )
    return make_response([_enrich(e, db) for e in events], rid)


@router.get("/summary", summary="Data quality summary counts")
def dq_summary(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
):
    rid = request.headers.get("X-Request-ID", "")
    all_events = _dq_repo.list(db, is_resolved=False, limit=10_000)

    total = len(all_events)
    severity_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for e in all_events:
        severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1
        type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1

    return make_response({
        "total": total,
        "critical": severity_counts.get("critical", 0),
        "warning": severity_counts.get("warning", 0),
        "info": severity_counts.get("info", 0),
        "sensor_faults": type_counts.get("FAULT", 0) + type_counts.get("sensor_fault", 0),
        "stale_data": type_counts.get("STALE", 0) + type_counts.get("stale_data", 0),
        "unresolved_by_type": type_counts,
        "total_unresolved": total,
    }, rid)
