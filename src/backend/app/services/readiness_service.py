"""
ReadinessService — bridges the ReadinessEngine with the database.

Loads current state from the DB, runs the deterministic engine,
and persists the result back to the asset_readiness table.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.ml.readiness import (
    ComponentState,
    MaintenanceStatus,
    ReadinessEngine,
    ReadinessInput,
    ReadinessOutput,
    ReadinessThresholds,
)
from app.repositories.fleet_repository import AssetRepository, ComponentRepository
from app.repositories.operations_repository import (
    PredictionRepository,
    ReadinessRepository,
    WorkOrderRepository,
    DataQualityRepository,
)


class ReadinessService:
    """Evaluate and persist asset readiness.

    Usage::

        svc = ReadinessService()
        output = svc.evaluate_asset(db, asset_id, mission_id=None)
    """

    def __init__(self, thresholds: ReadinessThresholds | None = None) -> None:
        self._engine = ReadinessEngine(thresholds=thresholds)
        self._asset_repo = AssetRepository()
        self._comp_repo = ComponentRepository()
        self._pred_repo = PredictionRepository()
        self._wo_repo = WorkOrderRepository()
        self._readiness_repo = ReadinessRepository()
        self._dq_repo = DataQualityRepository()

    def evaluate_asset(
        self,
        db: Session,
        asset_id: uuid.UUID,
        mission_id: uuid.UUID | None = None,
        mission_duration_hours: float = 0.0,
    ) -> ReadinessOutput:
        """Evaluate readiness for one asset and persist the result.

        Args:
            db:                     Active database session.
            asset_id:               Asset to evaluate.
            mission_id:             Optional mission context.
            mission_duration_hours: Duration of the mission window in hours.

        Returns:
            ReadinessOutput from the deterministic engine.

        Raises:
            ValueError: If the asset does not exist.
        """
        asset = self._asset_repo.get(db, asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")

        # --- Maintenance state ---
        blocking_wos = self._wo_repo.get_blocking_for_asset(db, asset_id)
        has_blocking = len(blocking_wos) > 0
        blocking_ids = [str(wo.id) for wo in blocking_wos]

        # Maintenance status: if any open WO is blocking AND marked IN_PROGRESS → UNDER_MAINTENANCE
        any_in_progress = any(wo.status == "IN_PROGRESS" for wo in blocking_wos)
        maint_status = (
            MaintenanceStatus.UNDER_MAINTENANCE
            if any_in_progress
            else MaintenanceStatus.OPERATIONAL
        )

        # --- Component states ---
        components = self._comp_repo.list_for_asset(db, asset_id)
        # All components are NOMINAL by default (no component-state table yet)
        component_states: dict[str, ComponentState] = {
            c.component_code: ComponentState.NOMINAL for c in components
        }
        critical_components: set[str] = set()  # Will be populated from component_type when available

        # --- ML predictions ---
        rul_pred = self._pred_repo.get_latest_for_asset(db, asset_id, "RUL")
        risk_pred = self._pred_repo.get_latest_for_asset(db, asset_id, "FAILURE_RISK")
        anomaly_pred = self._pred_repo.get_latest_for_asset(db, asset_id, "ANOMALY")

        rul_hours = rul_pred.rul_estimate if rul_pred else None
        rul_lower = rul_pred.rul_lower if rul_pred else None
        rul_upper = rul_pred.rul_upper if rul_pred else None
        failure_probability = risk_pred.failure_probability if risk_pred else None
        anomaly_score = anomaly_pred.anomaly_score if anomaly_pred else None

        # Use the latest prediction's confidence and observation count
        latest_pred = rul_pred or risk_pred or anomaly_pred
        prediction_confidence = latest_pred.confidence if latest_pred else None
        observation_count = latest_pred.observation_count if latest_pred else None

        # --- Telemetry freshness ---
        # Approximate from latest prediction timestamp
        hours_since_last_reading: float | None = None
        if latest_pred:
            delta = datetime.now(timezone.utc) - latest_pred.predicted_at.replace(tzinfo=timezone.utc)
            hours_since_last_reading = delta.total_seconds() / 3600.0

        # --- Data quality events ---
        dq_events = self._dq_repo.list(db, asset_id=asset_id, is_resolved=False, limit=50)
        stale_sensors = [e.description for e in dq_events if e.event_type == "STALE" and e.sensor_id]
        fault_sensors = [e.description for e in dq_events if e.event_type == "FAULT" and e.sensor_id]
        drifting_sensors = [e.description for e in dq_events if e.event_type == "DRIFT" and e.sensor_id]

        inp = ReadinessInput(
            asset_id=str(asset_id),
            asset_code=asset.asset_code,
            evaluated_at=datetime.now(timezone.utc),
            maintenance_status=maint_status,
            has_blocking_work_order=has_blocking,
            blocking_work_order_ids=blocking_ids,
            maintenance_overdue_hours=0.0,
            maintenance_is_critical=False,
            component_states=component_states,
            critical_components=critical_components,
            rul_hours=rul_hours,
            rul_lower=rul_lower,
            rul_upper=rul_upper,
            failure_probability=failure_probability,
            anomaly_score=anomaly_score,
            prediction_confidence=prediction_confidence,
            observation_count=observation_count,
            hours_since_last_reading=hours_since_last_reading,
            stale_sensor_codes=stale_sensors,
            fault_sensor_codes=fault_sensors,
            drifting_sensor_codes=drifting_sensors,
            mission_duration_hours=mission_duration_hours,
            mission_id=str(mission_id) if mission_id else None,
        )

        output = self._engine.evaluate(inp)

        # --- Persist result ---
        factors_json = json.dumps([
            {
                "code": f.code.value,
                "message": f.message,
                "severity": f.severity,
                "evidence": f.evidence,
            }
            for f in output.contributing_factors
        ])
        self._readiness_repo.upsert(db, asset_id, {
            "status": output.status.value,
            "primary_reason": output.primary_reason.value,
            "confidence": output.confidence,
            "factors_json": factors_json,
            "mission_id": mission_id,
            "evaluated_at": output.evaluated_at,
        })
        db.commit()

        return output

    def get_fleet_summary(self, db: Session) -> dict:
        """Return aggregate counts of each readiness status across the fleet."""
        all_readiness = self._readiness_repo.list(db)
        counts: dict[str, int] = {"READY": 0, "AT_RISK": 0, "NOT_READY": 0, "UNKNOWN": 0}
        for r in all_readiness:
            counts[r.status] = counts.get(r.status, 0) + 1
        total = sum(counts.values())
        return {"counts": counts, "total": total}
