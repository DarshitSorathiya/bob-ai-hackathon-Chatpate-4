"""
Pydantic schemas for the fleet domain (assets, components, sensors).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------

class AssetBase(BaseModel):
    asset_code: str = Field(..., max_length=50)
    asset_type: str = Field(..., max_length=100)
    call_sign: str | None = None
    description: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    commission_date: date | None = None
    total_hours: float = 0.0
    is_active: bool = True


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    call_sign: str | None = None
    description: str | None = None
    total_hours: float | None = None
    is_active: bool | None = None


class AssetResponse(AssetBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------

class ComponentBase(BaseModel):
    component_code: str = Field(..., max_length=100)
    component_type: str = Field(..., max_length=100)
    name: str = Field(..., max_length=200)
    manufacturer: str | None = None
    part_number: str | None = None
    installation_date: date | None = None
    total_hours: float = 0.0
    mtbf_hours: float | None = None
    is_active: bool = True


class ComponentCreate(ComponentBase):
    asset_id: uuid.UUID


class ComponentResponse(ComponentBase):
    id: uuid.UUID
    asset_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Sensor
# ---------------------------------------------------------------------------

class SensorBase(BaseModel):
    sensor_code: str = Field(..., max_length=100)
    sensor_type: str = Field(..., max_length=100)
    unit: str | None = None
    nominal_min: float | None = None
    nominal_max: float | None = None
    critical_min: float | None = None
    critical_max: float | None = None
    is_active: bool = True


class SensorCreate(SensorBase):
    component_id: uuid.UUID
    asset_id: uuid.UUID


class SensorResponse(SensorBase):
    id: uuid.UUID
    component_id: uuid.UUID
    asset_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
