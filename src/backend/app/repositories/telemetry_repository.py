"""Persistence helpers for telemetry history."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.telemetry import Telemetry


class TelemetryRepository:
    def create_many(self, db: Session, rows: list[dict]) -> list[Telemetry]:
        records = [Telemetry(**row) for row in rows]
        db.add_all(records)
        db.flush()
        return records

    def list_for_asset(
        self,
        db: Session,
        asset_id: uuid.UUID,
        *,
        since: datetime | None = None,
        limit: int = 10_000,
    ) -> list[Telemetry]:
        query = select(Telemetry).where(Telemetry.asset_id == asset_id)
        if since is not None:
            query = query.where(Telemetry.recorded_at >= since)
        query = query.order_by(Telemetry.recorded_at).limit(limit)
        return list(db.scalars(query))

    def get_latest_for_asset(self, db: Session, asset_id: uuid.UUID) -> Telemetry | None:
        """Return the most recent *sensor* observation, not an inference time."""
        return db.scalar(
            select(Telemetry)
            .where(Telemetry.asset_id == asset_id)
            .order_by(Telemetry.recorded_at.desc())
            .limit(1)
        )
