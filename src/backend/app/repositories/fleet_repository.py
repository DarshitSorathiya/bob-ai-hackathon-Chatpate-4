"""
Repository for fleet entities: assets, components, sensors.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fleet import Asset, Component, Sensor


class AssetRepository:
    def list(self, db: Session, *, skip: int = 0, limit: int = 100, active_only: bool = True) -> list[Asset]:
        q = select(Asset)
        if active_only:
            q = q.where(Asset.is_active == True)  # noqa: E712
        q = q.offset(skip).limit(limit).order_by(Asset.asset_code)
        return list(db.scalars(q))

    def get(self, db: Session, asset_id: uuid.UUID) -> Asset | None:
        return db.get(Asset, asset_id)

    def get_by_code(self, db: Session, asset_code: str) -> Asset | None:
        return db.scalar(select(Asset).where(Asset.asset_code == asset_code))

    def create(self, db: Session, data: dict) -> Asset:
        asset = Asset(**data)
        db.add(asset)
        db.flush()
        db.refresh(asset)
        return asset

    def update(self, db: Session, asset: Asset, data: dict) -> Asset:
        for k, v in data.items():
            if v is not None:
                setattr(asset, k, v)
        db.flush()
        db.refresh(asset)
        return asset

    def count(self, db: Session, *, active_only: bool = True) -> int:
        q = select(Asset)
        if active_only:
            q = q.where(Asset.is_active == True)  # noqa: E712
        return len(list(db.scalars(q)))


class ComponentRepository:
    def list_for_asset(self, db: Session, asset_id: uuid.UUID) -> list[Component]:
        return list(db.scalars(
            select(Component)
            .where(Component.asset_id == asset_id, Component.is_active == True)  # noqa: E712
            .order_by(Component.component_code)
        ))

    def get(self, db: Session, component_id: uuid.UUID) -> Component | None:
        return db.get(Component, component_id)

    def create(self, db: Session, data: dict) -> Component:
        comp = Component(**data)
        db.add(comp)
        db.flush()
        db.refresh(comp)
        return comp


class SensorRepository:
    def list_for_asset(self, db: Session, asset_id: uuid.UUID) -> list[Sensor]:
        return list(db.scalars(
            select(Sensor)
            .where(Sensor.asset_id == asset_id, Sensor.is_active == True)  # noqa: E712
            .order_by(Sensor.sensor_code)
        ))

    def list_for_component(self, db: Session, component_id: uuid.UUID) -> list[Sensor]:
        return list(db.scalars(
            select(Sensor)
            .where(Sensor.component_id == component_id, Sensor.is_active == True)  # noqa: E712
        ))

    def get(self, db: Session, sensor_id: uuid.UUID) -> Sensor | None:
        return db.get(Sensor, sensor_id)

    def create(self, db: Session, data: dict) -> Sensor:
        sensor = Sensor(**data)
        db.add(sensor)
        db.flush()
        db.refresh(sensor)
        return sensor
