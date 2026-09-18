"""Schemas for telemetry ingestion and prediction refresh requests."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TelemetryPointCreate(BaseModel):
    asset_id: uuid.UUID
    sensor_id: uuid.UUID
    component_id: uuid.UUID
    value: float
    recorded_at: datetime
    source: str = Field(default="operator", max_length=50)
    operating_hours: float | None = None
    operating_condition: str | None = Field(default=None, max_length=50)


class TelemetryBatchCreate(BaseModel):
    readings: list[TelemetryPointCreate] = Field(..., min_length=1, max_length=5000)
    refresh_predictions: bool = True


class TelemetryBatchResponse(BaseModel):
    accepted: int
    refreshed_assets: list[uuid.UUID]
    prediction_errors: list[str] = Field(default_factory=list)