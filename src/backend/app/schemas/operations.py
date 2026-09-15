"""
Pydantic schemas for operations: missions, work orders, alerts, readiness.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Mission
# ---------------------------------------------------------------------------

class CapabilityRequirementCreate(BaseModel):
    capability: str
    required_count: int = Field(1, ge=1)
    is_critical: bool = True
    notes: str | None = None


class MissionCreate(BaseModel):
    mission_code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=200)
    description: str | None = None
    priority: str = "MEDIUM"
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    duration_hours: float = Field(0.0, ge=0)
    location: str | None = None
    requirements: list[CapabilityRequirementCreate] = Field(default_factory=list)


class MissionUpdate(BaseModel):
    status: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    duration_hours: float | None = None
    location: str | None = None


class MissionRequirementResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    capability: str
    required_count: int
    is_critical: bool
    notes: str | None = None

    model_config = {"from_attributes": True}


class MissionResponse(BaseModel):
    id: uuid.UUID
    mission_code: str
    name: str
    description: str | None = None
    status: str
    priority: str
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    duration_hours: float
    location: str | None = None
    created_at: datetime
    updated_at: datetime
    requirements: list[MissionRequirementResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MissionAssignmentCreate(BaseModel):
    asset_id: uuid.UUID
    notes: str | None = None


class MissionAssignmentResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    asset_id: uuid.UUID
    status: str
    assigned_at: datetime
    notes: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Work order
# ---------------------------------------------------------------------------

class WorkOrderCreate(BaseModel):
    asset_id: uuid.UUID
    component_id: uuid.UUID | None = None
    title: str = Field(..., max_length=300)
    description: str | None = None
    priority: str = "MEDIUM"
    urgency_level: str = "SCHEDULED"
    is_blocking: bool = False
    estimated_hours: float | None = None
    scheduled_date: datetime | None = None


class WorkOrderUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    urgency_level: str | None = None
    is_blocking: bool | None = None
    actual_hours: float | None = None
    completed_date: datetime | None = None
    assigned_to: int | None = None


class WorkOrderResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    component_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    status: str
    priority: str
    urgency_level: str
    is_blocking: bool
    priority_score: float | None = None
    evidence: str | None = None
    estimated_hours: float | None = None
    actual_hours: float | None = None
    scheduled_date: datetime | None = None
    completed_date: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID | None = None
    component_id: uuid.UUID | None = None
    mission_id: uuid.UUID | None = None
    alert_type: str
    severity: str
    title: str
    message: str
    status: str
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertAcknowledge(BaseModel):
    pass  # current_user is used from token


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

class ContributingFactorResponse(BaseModel):
    code: str
    message: str
    severity: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class AssetReadinessResponse(BaseModel):
    asset_id: uuid.UUID
    asset_code: str
    status: str
    primary_reason: str
    confidence: float
    contributing_factors: list[ContributingFactorResponse] = Field(default_factory=list)
    evaluated_at: datetime
    mission_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

class PredictionResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    component_id: uuid.UUID | None = None
    prediction_type: str
    rul_estimate: float | None = None
    rul_lower: float | None = None
    rul_upper: float | None = None
    failure_probability: float | None = None
    anomaly_score: float | None = None
    confidence: float | None = None
    observation_count: int | None = None
    predicted_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

class DataQualityEventResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    sensor_id: uuid.UUID | None = None
    event_type: str
    severity: str
    description: str
    detected_at: datetime
    resolved_at: datetime | None = None
    is_resolved: bool

    model_config = {"from_attributes": True}
