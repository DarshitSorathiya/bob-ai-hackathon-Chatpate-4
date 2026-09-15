"""
/api/v1/alerts — alert listing and acknowledgement.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.responses import make_response
from app.repositories.operations_repository import AlertRepository
from app.schemas.operations import AlertResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])

_alert_repo = AlertRepository()


@router.get("", summary="List alerts")
def list_alerts(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    status_filter: str | None = None,
    severity: str | None = None,
    asset_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
):
    rid = request.headers.get("X-Request-ID", "")
    alerts = _alert_repo.list(
        db,
        asset_id=asset_id,
        status=status_filter,
        severity=severity,
        skip=skip,
        limit=limit,
    )
    return make_response([AlertResponse.model_validate(a).model_dump() for a in alerts], rid)


@router.get("/{alert_id}", summary="Get alert by ID")
def get_alert(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    alert_id: uuid.UUID,
):
    rid = request.headers.get("X-Request-ID", "")
    alert = _alert_repo.get(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return make_response(AlertResponse.model_validate(alert).model_dump(), rid)


@router.post("/{alert_id}/acknowledge", summary="Acknowledge an alert")
def acknowledge_alert(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    alert_id: uuid.UUID,
):
    rid = request.headers.get("X-Request-ID", "")
    alert = _alert_repo.get(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status not in ("ACTIVE",):
        raise HTTPException(status_code=400, detail=f"Alert is already {alert.status}")
    updated = _alert_repo.acknowledge(db, alert, current_user.id)
    db.commit()
    return make_response(AlertResponse.model_validate(updated).model_dump(), rid)
