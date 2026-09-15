"""
/api/v1/missions — mission planning and readiness evaluation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.responses import make_error, make_response
from app.ml.mission import MissionEngine
from app.ml.mission.models import AssetCapability, CapabilityRequirement as MLCapReq, MissionInput
from app.repositories.operations_repository import (
    MissionRepository,
    ReadinessRepository,
)
from app.repositories.fleet_repository import AssetRepository
from app.schemas.operations import MissionCreate, MissionAssignmentCreate, MissionResponse, MissionUpdate

router = APIRouter(prefix="/missions", tags=["missions"])

_mission_repo = MissionRepository()
_readiness_repo = ReadinessRepository()
_asset_repo = AssetRepository()
_engine = MissionEngine()


@router.get("", summary="List missions")
def list_missions(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
):
    rid = request.headers.get("X-Request-ID", "")
    missions = _mission_repo.list(db, skip=skip, limit=limit)
    return make_response([MissionResponse.model_validate(m).model_dump() for m in missions], rid)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create mission")
def create_mission(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    body: MissionCreate,
):
    rid = request.headers.get("X-Request-ID", "")
    existing = _mission_repo.get_by_code(db, body.mission_code)
    if existing:
        return make_error("MISSION_EXISTS", f"Mission code '{body.mission_code}' already exists.", rid)

    requirements = body.requirements
    data = body.model_dump(exclude={"requirements"})
    mission = _mission_repo.create(db, data)

    for req in requirements:
        _mission_repo.add_requirement(db, {
            "mission_id": mission.id,
            **req.model_dump(),
        })

    db.commit()
    db.refresh(mission)
    return make_response(MissionResponse.model_validate(mission).model_dump(), rid)


@router.get("/{mission_id}", summary="Get mission by ID")
def get_mission(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    mission_id: uuid.UUID,
):
    rid = request.headers.get("X-Request-ID", "")
    mission = _mission_repo.get(db, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return make_response(MissionResponse.model_validate(mission).model_dump(), rid)


@router.patch("/{mission_id}", summary="Update mission status/details")
def update_mission(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    mission_id: uuid.UUID,
    body: MissionUpdate,
):
    rid = request.headers.get("X-Request-ID", "")
    mission = _mission_repo.get(db, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    updated = _mission_repo.update(db, mission, body.model_dump(exclude_none=True))
    db.commit()
    return make_response(MissionResponse.model_validate(updated).model_dump(), rid)


@router.post("/{mission_id}/assignments", status_code=status.HTTP_201_CREATED, summary="Assign asset to mission")
def assign_asset(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    mission_id: uuid.UUID,
    body: MissionAssignmentCreate,
):
    rid = request.headers.get("X-Request-ID", "")
    mission = _mission_repo.get(db, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    asset = _asset_repo.get(db, body.asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    assignment = _mission_repo.add_assignment(db, {
        "mission_id": mission_id,
        "asset_id": body.asset_id,
        "assigned_by": current_user.id,
        "notes": body.notes,
    })
    db.commit()
    return make_response({"id": str(assignment.id), "asset_id": str(body.asset_id), "mission_id": str(mission_id)}, rid)


@router.get("/{mission_id}/readiness", summary="Evaluate mission-level readiness")
def get_mission_readiness(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    mission_id: uuid.UUID,
):
    """Evaluate readiness of all assigned assets against mission requirements.

    Uses the deterministic MissionEngine — no LLM involved.
    """
    rid = request.headers.get("X-Request-ID", "")
    mission = _mission_repo.get(db, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    # Build requirements
    ml_reqs = [
        MLCapReq(
            capability=r.capability,
            required_count=r.required_count,
            is_critical=r.is_critical,
        )
        for r in mission.requirements
    ]

    # Build assigned asset capabilities from readiness DB records
    assignments = _mission_repo.list_assignments(db, mission_id)
    assigned_assets: list[AssetCapability] = []
    for asgn in assignments:
        asset = _asset_repo.get(db, asgn.asset_id)
        if not asset:
            continue
        rec = _readiness_repo.get_for_asset(db, asgn.asset_id)
        status_val = rec.status if rec else "UNKNOWN"
        confidence = rec.confidence if rec else 0.0
        primary_reason = rec.primary_reason if rec else "NO_PREDICTION_AVAILABLE"
        # Infer capabilities from asset_type (simplified — real impl would use a capabilities table)
        caps = {asset.asset_type}
        assigned_assets.append(AssetCapability(
            asset_id=str(asgn.asset_id),
            asset_code=asset.asset_code,
            capabilities=caps,
            readiness_status=status_val,
            readiness_confidence=confidence,
            primary_reason=primary_reason,
            is_assigned=True,
            assigned_mission_ids=[str(mission_id)],
        ))

    # Build fleet asset list for substitution search
    all_assets = _asset_repo.list(db, limit=500)
    fleet_assets: list[AssetCapability] = []
    assigned_ids = {a.asset_id for a in assigned_assets}
    for asset in all_assets:
        if str(asset.id) in assigned_ids:
            continue
        rec = _readiness_repo.get_for_asset(db, asset.id)
        status_val = rec.status if rec else "UNKNOWN"
        confidence = rec.confidence if rec else 0.0
        primary_reason = rec.primary_reason if rec else "NO_PREDICTION_AVAILABLE"
        fleet_assets.append(AssetCapability(
            asset_id=str(asset.id),
            asset_code=asset.asset_code,
            capabilities={asset.asset_type},
            readiness_status=status_val,
            readiness_confidence=confidence,
            primary_reason=primary_reason,
        ))

    inp = MissionInput(
        mission_id=str(mission_id),
        mission_code=mission.mission_code,
        mission_window_hours=mission.duration_hours,
        start_time=mission.planned_start or datetime.now(timezone.utc),
        requirements=ml_reqs,
        assigned_assets=assigned_assets,
        fleet_assets=fleet_assets,
        evaluated_at=datetime.now(timezone.utc),
    )

    output = _engine.evaluate(inp)

    return make_response({
        "mission_id": output.mission_id,
        "mission_code": output.mission_code,
        "status": output.status.value,
        "risk_level": output.risk_level.value,
        "risk_score": output.risk_score,
        "summary": output.summary,
        "gaps": [
            {
                "capability": g.capability,
                "required_count": g.required_count,
                "available_count": g.available_count,
                "at_risk_count": g.at_risk_count,
                "is_critical": g.is_critical,
                "shortage": g.shortage,
                "substitutions": [
                    {
                        "asset_id": s.asset_id,
                        "asset_code": s.asset_code,
                        "readiness_status": s.readiness_status,
                        "suitability_score": s.suitability_score,
                        "reason": s.reason,
                    }
                    for s in g.substitutions
                ],
            }
            for g in output.gaps
        ],
        "conflicts": [
            {
                "asset_id": c.asset_id,
                "asset_code": c.asset_code,
                "conflict_type": c.conflict_type,
                "description": c.description,
            }
            for c in output.conflicts
        ],
        "capability_readiness": [
            {
                "capability": cr.capability,
                "required_count": cr.required_count,
                "ready_assets": cr.ready_assets,
                "at_risk_assets": cr.at_risk_assets,
                "not_ready_assets": cr.not_ready_assets,
                "unknown_assets": cr.unknown_assets,
            }
            for cr in output.capability_readiness
        ],
        "contributing_factors": output.contributing_factors,
        "evaluated_at": output.evaluated_at.isoformat(),
    }, rid)
