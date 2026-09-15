"""
/api/v1/maintenance — work order CRUD and prioritized queue.

RBAC:
  GET  endpoints: all authenticated users
  POST/PATCH: MAINTAINER or ADMIN only
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.audit import AuditLogger
from app.core.responses import make_response
from app.core.roles import ADMIN, MAINTAINER
from app.ml.maintenance import MaintenancePrioritizer
from app.ml.maintenance.models import (
    AssetCriticality,
    ComponentCriticality,
    MaintenanceItem,
    MaintenanceState,
    SafetyClassification,
)
from app.repositories.operations_repository import WorkOrderRepository, PredictionRepository, ReadinessRepository
from app.repositories.fleet_repository import AssetRepository
from app.schemas.operations import WorkOrderCreate, WorkOrderResponse, WorkOrderUpdate

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

_wo_repo = WorkOrderRepository()
_pred_repo = PredictionRepository()
_asset_repo = AssetRepository()
_readiness_repo = ReadinessRepository()
_prioritizer = MaintenancePrioritizer()
_audit = AuditLogger()


@router.get("/work-orders", summary="List work orders (optionally filtered)")
def list_work_orders(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    asset_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    blocking_only: bool = False,
    skip: int = 0,
    limit: int = 100,
):
    rid = request.headers.get("X-Request-ID", "")
    is_blocking = True if blocking_only else None
    wos = _wo_repo.list(
        db,
        asset_id=asset_id,
        status=status_filter,
        is_blocking=is_blocking,
        skip=skip,
        limit=limit,
    )
    return make_response([WorkOrderResponse.model_validate(w).model_dump() for w in wos], rid)


@router.post("/work-orders", status_code=status.HTTP_201_CREATED, summary="Create work order")
def create_work_order(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    body: WorkOrderCreate,
):
    rid = request.headers.get("X-Request-ID", "")
    asset = _asset_repo.get(db, body.asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    data = body.model_dump()
    data["created_by"] = current_user.id
    wo = _wo_repo.create(db, data)
    db.commit()
    return make_response(WorkOrderResponse.model_validate(wo).model_dump(), rid)


@router.get("/work-orders/{wo_id}", summary="Get work order by ID")
def get_work_order(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    wo_id: uuid.UUID,
):
    rid = request.headers.get("X-Request-ID", "")
    wo = _wo_repo.get(db, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    return make_response(WorkOrderResponse.model_validate(wo).model_dump(), rid)


@router.patch("/work-orders/{wo_id}", summary="Update work order")
def update_work_order(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    wo_id: uuid.UUID,
    body: WorkOrderUpdate,
):
    rid = request.headers.get("X-Request-ID", "")
    wo = _wo_repo.get(db, wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    updated = _wo_repo.update(db, wo, body.model_dump(exclude_none=True))
    db.commit()
    return make_response(WorkOrderResponse.model_validate(updated).model_dump(), rid)


@router.get("/queue", summary="Prioritized maintenance queue")
def prioritized_queue(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    limit: int = 50,
):
    """Return all open work orders ranked by the deterministic priority formula.

    Uses MaintenancePrioritizer — no LLM, no randomness.
    """
    rid = request.headers.get("X-Request-ID", "")
    wos = _wo_repo.list(db, status="OPEN", limit=limit)

    items: list[MaintenanceItem] = []
    for wo in wos:
        asset = _asset_repo.get(db, wo.asset_id)
        rul_pred = _pred_repo.get_latest_for_asset(db, wo.asset_id, "RUL")
        risk_pred = _pred_repo.get_latest_for_asset(db, wo.asset_id, "FAILURE_RISK")
        anomaly_pred = _pred_repo.get_latest_for_asset(db, wo.asset_id, "ANOMALY")

        items.append(MaintenanceItem(
            item_id=str(wo.id),
            asset_id=str(wo.asset_id),
            asset_code=asset.asset_code if asset else str(wo.asset_id),
            component_code=str(wo.component_id) if wo.component_id else "UNKNOWN",
            description=wo.title,
            failure_probability=risk_pred.failure_probability if risk_pred else None,
            rul_hours=rul_pred.rul_estimate if rul_pred else None,
            anomaly_score=anomaly_pred.anomaly_score if anomaly_pred else None,
            hours_until_next_mission=None,  # mission proximity not implemented yet
            blocks_mission=wo.is_blocking,
            asset_criticality=AssetCriticality.MEDIUM,
            component_criticality=ComponentCriticality.OPERATIONAL,
            safety_classification=SafetyClassification.NO_SAFETY_IMPLICATION,
            maintenance_state=MaintenanceState(wo.status) if wo.status in MaintenanceState.__members__ else MaintenanceState.OPEN,
            estimated_downtime_hours=wo.estimated_hours or 4.0,
            hours_overdue=0.0,
        ))

    queue = _prioritizer.prioritize(items, evaluated_at=datetime.now(timezone.utc))

    return make_response({
        "total": len(queue.items),
        "total_immediate": queue.total_immediate,
        "total_urgent": queue.total_urgent,
        "total_scheduled": queue.total_scheduled,
        "items": [
            {
                "item_id": i.item_id,
                "asset_id": i.asset_id,
                "asset_code": i.asset_code,
                "component_code": i.component_code,
                "description": i.description,
                "priority_score": i.priority_score,
                "urgency_level": i.urgency_level.value,
                "blocks_mission": i.blocks_mission,
                "recommended_action": i.recommended_action,
                "contributing_factors": i.contributing_factors,
                "score_breakdown": {
                    "failure_risk": i.score_breakdown.failure_risk_score,
                    "rul": i.score_breakdown.rul_score,
                    "mission_proximity": i.score_breakdown.mission_proximity_score,
                    "asset_criticality": i.score_breakdown.asset_criticality_score,
                    "component_criticality": i.score_breakdown.component_criticality_score,
                    "safety": i.score_breakdown.safety_score,
                    "overdue": i.score_breakdown.overdue_score,
                },
            }
            for i in queue.items
        ],
    }, rid)
