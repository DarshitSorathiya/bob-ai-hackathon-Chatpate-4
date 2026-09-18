"""Telemetry ingestion and model-refresh endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import CurrentUser, DbSession
from app.core.responses import make_response
from app.models.fleet import Asset, Component, Sensor
from app.repositories.telemetry_repository import TelemetryRepository
from app.schemas.telemetry import TelemetryBatchCreate, TelemetryBatchResponse
from app.services.inference_service import InferenceService

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
_telemetry_repo = TelemetryRepository()
_inference_service = InferenceService()


@router.post("/batch", summary="Ingest telemetry and refresh predictions")
def ingest_batch(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    body: TelemetryBatchCreate,
):
    rid = request.headers.get("X-Request-ID", "")
    asset_ids: set[uuid.UUID] = set()
    rows: list[dict] = []

    for point in body.readings:
        asset = db.get(Asset, point.asset_id)
        sensor = db.get(Sensor, point.sensor_id)
        component = db.get(Component, point.component_id)
        if not asset or not sensor or not component:
            raise HTTPException(status_code=404, detail="Telemetry references an unknown asset, sensor, or component")
        if sensor.asset_id != point.asset_id or sensor.component_id != point.component_id or component.asset_id != point.asset_id:
            raise HTTPException(status_code=400, detail="Telemetry asset, component, and sensor ownership must match")
        asset_ids.add(point.asset_id)
        rows.append(point.model_dump())

    _telemetry_repo.create_many(db, rows)
    db.commit()

    errors: list[str] = []
    refreshed: list[uuid.UUID] = []
    if body.refresh_predictions:
        for asset_id in asset_ids:
            try:
                _inference_service.process_asset(db, asset_id)
                refreshed.append(asset_id)
            except Exception as exc:
                db.rollback()
                errors.append(f"{asset_id}: {exc}")

    return make_response(TelemetryBatchResponse(
        accepted=len(rows),
        refreshed_assets=refreshed,
        prediction_errors=errors,
    ).model_dump(), rid)