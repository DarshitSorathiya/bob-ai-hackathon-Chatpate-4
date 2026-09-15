"""
Repository for operations: missions, work orders, alerts, readiness, predictions.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operations import (
    Alert,
    AssetReadiness,
    Mission,
    MissionAssignment,
    MissionRequirement,
    WorkOrder,
)
from app.models.telemetry import DataQualityEvent, Prediction


class MissionRepository:
    def list(self, db: Session, *, skip: int = 0, limit: int = 50) -> list[Mission]:
        return list(db.scalars(
            select(Mission).order_by(Mission.planned_start).offset(skip).limit(limit)
        ))

    def get(self, db: Session, mission_id: uuid.UUID) -> Mission | None:
        return db.get(Mission, mission_id)

    def get_by_code(self, db: Session, code: str) -> Mission | None:
        return db.scalar(select(Mission).where(Mission.mission_code == code))

    def create(self, db: Session, data: dict) -> Mission:
        mission = Mission(**data)
        db.add(mission)
        db.flush()
        db.refresh(mission)
        return mission

    def update(self, db: Session, mission: Mission, data: dict) -> Mission:
        for k, v in data.items():
            if v is not None:
                setattr(mission, k, v)
        db.flush()
        db.refresh(mission)
        return mission

    def add_requirement(self, db: Session, data: dict) -> MissionRequirement:
        req = MissionRequirement(**data)
        db.add(req)
        db.flush()
        db.refresh(req)
        return req

    def add_assignment(self, db: Session, data: dict) -> MissionAssignment:
        assignment = MissionAssignment(**data)
        db.add(assignment)
        db.flush()
        db.refresh(assignment)
        return assignment

    def list_assignments(self, db: Session, mission_id: uuid.UUID) -> list[MissionAssignment]:
        return list(db.scalars(
            select(MissionAssignment).where(MissionAssignment.mission_id == mission_id)
        ))


class WorkOrderRepository:
    def list(
        self, db: Session,
        *,
        asset_id: uuid.UUID | None = None,
        status: str | None = None,
        is_blocking: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[WorkOrder]:
        q = select(WorkOrder).where(WorkOrder.is_active == True)  # noqa: E712
        if asset_id:
            q = q.where(WorkOrder.asset_id == asset_id)
        if status:
            q = q.where(WorkOrder.status == status)
        if is_blocking is not None:
            q = q.where(WorkOrder.is_blocking == is_blocking)
        q = q.order_by(WorkOrder.priority_score.desc().nullslast()).offset(skip).limit(limit)
        return list(db.scalars(q))

    def get(self, db: Session, wo_id: uuid.UUID) -> WorkOrder | None:
        return db.get(WorkOrder, wo_id)

    def get_blocking_for_asset(self, db: Session, asset_id: uuid.UUID) -> list[WorkOrder]:
        return list(db.scalars(
            select(WorkOrder).where(
                WorkOrder.asset_id == asset_id,
                WorkOrder.is_blocking == True,  # noqa: E712
                WorkOrder.status.in_(["OPEN", "IN_PROGRESS", "AWAITING_PARTS"]),
                WorkOrder.is_active == True,  # noqa: E712
            )
        ))

    def create(self, db: Session, data: dict) -> WorkOrder:
        wo = WorkOrder(**data)
        db.add(wo)
        db.flush()
        db.refresh(wo)
        return wo

    def update(self, db: Session, wo: WorkOrder, data: dict) -> WorkOrder:
        for k, v in data.items():
            if v is not None:
                setattr(wo, k, v)
        db.flush()
        db.refresh(wo)
        return wo


class AlertRepository:
    def list(
        self, db: Session,
        *,
        asset_id: uuid.UUID | None = None,
        status: str | None = None,
        severity: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Alert]:
        q = select(Alert)
        if asset_id:
            q = q.where(Alert.asset_id == asset_id)
        if status:
            q = q.where(Alert.status == status)
        if severity:
            q = q.where(Alert.severity == severity)
        q = q.order_by(Alert.created_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(q))

    def get(self, db: Session, alert_id: uuid.UUID) -> Alert | None:
        return db.get(Alert, alert_id)

    def create(self, db: Session, data: dict) -> Alert:
        alert = Alert(**data)
        db.add(alert)
        db.flush()
        db.refresh(alert)
        return alert

    def acknowledge(self, db: Session, alert: Alert, user_id: int) -> Alert:
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.utcnow()
        db.flush()
        db.refresh(alert)
        return alert


class ReadinessRepository:
    def get_for_asset(self, db: Session, asset_id: uuid.UUID) -> AssetReadiness | None:
        return db.scalar(select(AssetReadiness).where(AssetReadiness.asset_id == asset_id))

    def list(self, db: Session, *, status: str | None = None) -> list[AssetReadiness]:
        q = select(AssetReadiness)
        if status:
            q = q.where(AssetReadiness.status == status)
        return list(db.scalars(q))

    def upsert(self, db: Session, asset_id: uuid.UUID, data: dict) -> AssetReadiness:
        existing = self.get_for_asset(db, asset_id)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            db.flush()
            db.refresh(existing)
            return existing
        rec = AssetReadiness(asset_id=asset_id, **data)
        db.add(rec)
        db.flush()
        db.refresh(rec)
        return rec


class PredictionRepository:
    def get_latest_for_asset(self, db: Session, asset_id: uuid.UUID, prediction_type: str | None = None) -> Prediction | None:
        q = select(Prediction).where(Prediction.asset_id == asset_id)
        if prediction_type:
            q = q.where(Prediction.prediction_type == prediction_type)
        q = q.order_by(Prediction.predicted_at.desc()).limit(1)
        return db.scalar(q)

    def list_for_asset(self, db: Session, asset_id: uuid.UUID, *, limit: int = 20) -> list[Prediction]:
        return list(db.scalars(
            select(Prediction)
            .where(Prediction.asset_id == asset_id)
            .order_by(Prediction.predicted_at.desc())
            .limit(limit)
        ))

    def create(self, db: Session, data: dict) -> Prediction:
        pred = Prediction(**data)
        db.add(pred)
        db.flush()
        db.refresh(pred)
        return pred


class DataQualityRepository:
    def list(
        self, db: Session,
        *,
        asset_id: uuid.UUID | None = None,
        severity: str | None = None,
        event_type: str | None = None,
        is_resolved: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DataQualityEvent]:
        q = select(DataQualityEvent)
        if asset_id:
            q = q.where(DataQualityEvent.asset_id == asset_id)
        if severity:
            q = q.where(DataQualityEvent.severity == severity)
        if event_type:
            q = q.where(DataQualityEvent.event_type == event_type)
        if is_resolved is not None:
            q = q.where(DataQualityEvent.is_resolved == is_resolved)
        q = q.order_by(DataQualityEvent.detected_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(q))

    def create(self, db: Session, data: dict) -> DataQualityEvent:
        evt = DataQualityEvent(**data)
        db.add(evt)
        db.flush()
        db.refresh(evt)
        return evt
