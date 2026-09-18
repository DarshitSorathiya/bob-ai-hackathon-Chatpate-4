"""
/api/v1/assets — asset CRUD and per-asset sub-resources.

RBAC:
  GET  endpoints: all authenticated users
  POST/PATCH endpoints: MAINTAINER or ADMIN only
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.audit import AuditLogger
from app.core.responses import make_error, make_response
from app.core.roles import ADMIN, MAINTAINER
from app.repositories.fleet_repository import AssetRepository, ComponentRepository, SensorRepository
from app.repositories.operations_repository import AlertRepository, PredictionRepository, ReadinessRepository
from app.schemas.fleet import AssetCreate, AssetResponse, AssetUpdate, ComponentCreate, ComponentResponse, SensorResponse
from app.schemas.operations import AlertResponse, AssetReadinessResponse, ContributingFactorResponse, PredictionResponse
from app.services.readiness_service import ReadinessService

router = APIRouter(prefix="/assets", tags=["assets"])

_asset_repo = AssetRepository()
_comp_repo = ComponentRepository()
_sensor_repo = SensorRepository()
_pred_repo = PredictionRepository()
_alert_repo = AlertRepository()
_readiness_repo = ReadinessRepository()
_audit = AuditLogger()
_readiness_service = ReadinessService()


@router.get("", summary="List all active assets")
def list_assets(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
):
    rid = request.headers.get("X-Request-ID", "")
    assets = _asset_repo.list(db, skip=skip, limit=limit)
    return make_response([AssetResponse.model_validate(a).model_dump() for a in assets], rid)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create asset",
             dependencies=[Depends(require_roles(MAINTAINER, ADMIN))])
def create_asset(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    body: AssetCreate,
):
    rid = request.headers.get("X-Request-ID", "")
    existing = _asset_repo.get_by_code(db, body.asset_code)
    if existing:
        return make_error("ASSET_EXISTS", f"Asset code '{body.asset_code}' already exists.", rid)
    asset = _asset_repo.create(db, body.model_dump())
    component = _comp_repo.create(db, {
        "asset_id": asset.id,
        "component_code": f"{asset.asset_code}-ENGINE",
        "component_type": "ENGINE_CORE",
        "name": f"{asset.asset_code} Engine Core",
        "mtbf_hours": 12000.0,
    })
    _sensor_repo.create(db, {
        "asset_id": asset.id,
        "component_id": component.id,
        "sensor_code": f"{asset.asset_code}-TEMP",
        "sensor_type": "TEMPERATURE",
        "unit": "°C",
        "nominal_min": 20.0,
        "nominal_max": 120.0,
        "critical_min": 0.0,
        "critical_max": 160.0,
    })
    _sensor_repo.create(db, {
        "asset_id": asset.id,
        "component_id": component.id,
        "sensor_code": f"{asset.asset_code}-VIB",
        "sensor_type": "VIBRATION",
        "unit": "mm/s",
        "nominal_min": 0.0,
        "nominal_max": 12.0,
        "critical_min": 0.0,
        "critical_max": 25.0,
    })
    # New aircraft start as UNKNOWN, never implicitly mission-ready.  The
    # lifecycle worker (or telemetry batch endpoint) will build the time-series
    # history and then invoke the registered models automatically.
    _readiness_service.evaluate_asset(db, asset.id, commit=False)
    _audit.log(db, action="asset.create", user_id=current_user.id,
               resource_type="asset", resource_id=str(asset.id), request_id=rid)
    db.commit()
    return make_response(AssetResponse.model_validate(asset).model_dump(), rid)


@router.get("/{asset_id}", summary="Get asset by ID")
def get_asset(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    asset_id: uuid.UUID,
):
    rid = request.headers.get("X-Request-ID", "")
    asset = _asset_repo.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return make_response(AssetResponse.model_validate(asset).model_dump(), rid)


@router.patch("/{asset_id}", summary="Update asset",
              dependencies=[Depends(require_roles(MAINTAINER, ADMIN))])
def update_asset(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    asset_id: uuid.UUID,
    body: AssetUpdate,
):
    rid = request.headers.get("X-Request-ID", "")
    asset = _asset_repo.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    updated = _asset_repo.update(db, asset, body.model_dump(exclude_none=True))
    _audit.log(db, action="asset.update", user_id=current_user.id,
               resource_type="asset", resource_id=str(asset_id), request_id=rid)
    db.commit()
    return make_response(AssetResponse.model_validate(updated).model_dump(), rid)


@router.get("/{asset_id}/components", summary="List components for an asset")
def list_components(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    asset_id: uuid.UUID,
):
    rid = request.headers.get("X-Request-ID", "")
    asset = _asset_repo.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    comps = _comp_repo.list_for_asset(db, asset_id)
    return make_response([ComponentResponse.model_validate(c).model_dump() for c in comps], rid)


@router.post(
    "/{asset_id}/components",
    status_code=status.HTTP_201_CREATED,
    summary="Add component to asset",
    dependencies=[Depends(require_roles(MAINTAINER, ADMIN))],
)
def create_component(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    asset_id: uuid.UUID,
    body: ComponentCreate,
):
    rid = request.headers.get("X-Request-ID", "")
    asset = _asset_repo.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    data = body.model_dump()
    data["asset_id"] = asset_id
    comp = _comp_repo.create(db, data)
    db.commit()
    return make_response(ComponentResponse.model_validate(comp).model_dump(), rid)


@router.get("/{asset_id}/sensors", summary="List sensors for an asset")
def list_sensors(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    asset_id: uuid.UUID,
):
    rid = request.headers.get("X-Request-ID", "")
    asset = _asset_repo.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    sensors = _sensor_repo.list_for_asset(db, asset_id)
    return make_response([SensorResponse.model_validate(s).model_dump() for s in sensors], rid)


@router.get("/{asset_id}/predictions", summary="List predictions for an asset")
def list_predictions(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    asset_id: uuid.UUID,
    limit: int = 20,
):
    rid = request.headers.get("X-Request-ID", "")
    asset = _asset_repo.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    preds = _pred_repo.list_for_asset(db, asset_id, limit=limit)
    return make_response([PredictionResponse.model_validate(p).model_dump() for p in preds], rid)


@router.get("/{asset_id}/readiness", summary="Get current readiness for an asset")
def get_readiness(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    asset_id: uuid.UUID,
):
    rid = request.headers.get("X-Request-ID", "")
    asset = _asset_repo.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    rec = _readiness_repo.get_for_asset(db, asset_id)
    if not rec:
        # Return UNKNOWN if no evaluation has been run yet
        return make_response({
            "asset_id": str(asset_id),
            "asset_code": asset.asset_code,
            "status": "UNKNOWN",
            "primary_reason": "NO_PREDICTION_AVAILABLE",
            "confidence": 0.0,
            "contributing_factors": [],
            "evaluated_at": None,
            "mission_id": None,
        }, rid)

    import json
    factors = []
    if rec.factors_json:
        factors = json.loads(rec.factors_json)

    return make_response({
        "asset_id": str(asset_id),
        "asset_code": asset.asset_code,
        "status": rec.status,
        "primary_reason": rec.primary_reason,
        "confidence": rec.confidence,
        "contributing_factors": factors,
        "evaluated_at": rec.evaluated_at.isoformat() if rec.evaluated_at else None,
        "mission_id": str(rec.mission_id) if rec.mission_id else None,
    }, rid)


@router.get("/{asset_id}/alerts", summary="List alerts for an asset")
def list_asset_alerts(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    asset_id: uuid.UUID,
    status_filter: str | None = None,
):
    rid = request.headers.get("X-Request-ID", "")
    asset = _asset_repo.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    alerts = _alert_repo.list(db, asset_id=asset_id, status=status_filter)
    return make_response([AlertResponse.model_validate(a).model_dump() for a in alerts], rid)
