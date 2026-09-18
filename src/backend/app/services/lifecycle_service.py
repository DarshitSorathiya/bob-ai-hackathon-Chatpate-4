"""Background fleet lifecycle updates for telemetry and mission state."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fleet import Asset, Sensor
from app.models.operations import Mission
from app.repositories.telemetry_repository import TelemetryRepository
from app.services.inference_service import InferenceService


class FleetLifecycleService:
    """Advance simulated fleet state and refresh model-backed decisions."""

    def __init__(self) -> None:
        self.telemetry_repo = TelemetryRepository()
        self.inference_service = InferenceService()

    def tick(self, db: Session, simulation_hours: float = 1.0) -> dict[str, int | float]:
        """Advance the fleet by a logical time interval.

        ``simulation_hours`` is deliberately explicit: production can pass
        wall-clock elapsed hours, while the demo worker can advance one
        simulated hour per tick.  Every resulting record gets a monotonic
        logical timestamp, so rolling time-series features evolve correctly.
        """
        if simulation_hours <= 0:
            raise ValueError("simulation_hours must be positive")
        now = datetime.now(timezone.utc)
        self._advance_missions(db, now)
        assets = list(db.scalars(select(Asset).where(Asset.is_active.is_(True))))
        generated = 0
        refreshed = 0

        for asset in assets:
            asset.total_hours = float(asset.total_hours or 0.0) + simulation_hours
            sensors = list(db.scalars(select(Sensor).where(
                Sensor.asset_id == asset.id,
                Sensor.is_active.is_(True),
            )))
            latest = self.telemetry_repo.get_latest_for_asset(db, asset.id)
            logical_now = (
                latest.recorded_at.replace(tzinfo=timezone.utc)
                if latest and latest.recorded_at.tzinfo is None
                else latest.recorded_at if latest else now
            ) + timedelta(hours=simulation_hours)
            rows = [self._reading(asset, sensor, logical_now) for sensor in sensors]
            if rows:
                self.telemetry_repo.create_many(db, rows)
                generated += len(rows)
            db.flush()
            try:
                self.inference_service.process_asset(db, asset.id)
                refreshed += 1
            except Exception:
                db.rollback()

        db.commit()
        return {
            "assets": len(assets), "telemetry": generated, "refreshed": refreshed,
            "simulation_hours": simulation_hours,
        }

    def _advance_missions(self, db: Session, now: datetime) -> None:
        missions = list(db.scalars(select(Mission)))
        for mission in missions:
            if mission.status in {"COMPLETED", "CANCELLED"} or not mission.planned_start:
                continue
            start = mission.planned_start
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            end = mission.planned_end or start + timedelta(hours=mission.duration_hours)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if now >= end:
                mission.status = "COMPLETED"
            elif now >= start:
                mission.status = "ACTIVE"

    @staticmethod
    def _reading(asset: Asset, sensor: Sensor, now: datetime) -> dict:
        """Generate a deterministic condition-dependent reading for one sensor."""
        nominal_min = sensor.nominal_min if sensor.nominal_min is not None else 0.0
        nominal_max = sensor.nominal_max if sensor.nominal_max is not None else 1.0
        midpoint = (nominal_min + nominal_max) / 2.0
        span = max(0.001, nominal_max - nominal_min)
        health = max(0.05, 1.0 - (float(asset.total_hours or 0.0) / 12_000.0))
        phase = (now.timestamp() // 3600) % 24
        rng = random.Random(f"{asset.id}:{sensor.id}:{int(phase)}")
        degradation = (1.0 - health) * span * (1.5 if "VIB" in sensor.sensor_type.upper() else 0.6)
        value = midpoint + degradation + rng.gauss(0.0, span * 0.02)
        critical_min = sensor.critical_min if sensor.critical_min is not None else nominal_min
        critical_max = sensor.critical_max if sensor.critical_max is not None else nominal_max
        return {
            "asset_id": asset.id,
            "sensor_id": sensor.id,
            "component_id": sensor.component_id,
            "value": max(critical_min, min(critical_max, value)),
            "recorded_at": now,
            "source": "background_simulator",
            "operating_hours": asset.total_hours,
            "operating_condition": "MISSION" if phase in {8, 9, 10, 11, 12, 13, 14, 15} else "CRUISE",
        }
