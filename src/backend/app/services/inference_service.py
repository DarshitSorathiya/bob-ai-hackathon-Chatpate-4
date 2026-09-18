"""Run registered ML models on stored telemetry and refresh readiness."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app.ml.features import FeaturePipeline
from app.ml.models.inference import AnomalyInference, FailureInference, RULInference
from app.ml.models.registry import ModelRegistry
from app.models.telemetry import Prediction
from app.repositories.fleet_repository import AssetRepository, ComponentRepository, SensorRepository
from app.repositories.operations_repository import PredictionRepository
from app.repositories.telemetry_repository import TelemetryRepository
from app.services.readiness_service import ReadinessService


class InferenceService:
    """Orchestrate feature generation, model inference, persistence, and readiness."""

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self.telemetry_repo = TelemetryRepository()
        self.asset_repo = AssetRepository()
        self.component_repo = ComponentRepository()
        self.sensor_repo = SensorRepository()
        self.prediction_repo = PredictionRepository()
        self.readiness_service = ReadinessService()

    def process_asset(self, db: Session, asset_id: uuid.UUID) -> list[Prediction]:
        asset = self.asset_repo.get(db, asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")

        telemetry = self.telemetry_repo.list_for_asset(db, asset_id)
        sensors = self.sensor_repo.list_for_asset(db, asset_id)
        components = self.component_repo.list_for_asset(db, asset_id)
        if not telemetry or not sensors or not components:
            self.readiness_service.evaluate_asset(db, asset_id)
            db.commit()
            return []

        telemetry_df = pd.DataFrame([
            {
                "asset_id": str(row.asset_id),
                "sensor_id": str(row.sensor_id),
                "component_id": str(row.component_id),
                "value": row.value,
                "recorded_at": row.recorded_at,
                "source": row.source,
                "operating_hours": row.operating_hours,
                "operating_condition": row.operating_condition,
            }
            for row in telemetry
        ])
        sensors_df = pd.DataFrame([
            {
                "sensor_id": str(sensor.id),
                "sensor_type": sensor.sensor_type,
                "nominal_min": sensor.nominal_min,
                "nominal_max": sensor.nominal_max,
                "critical_min": sensor.critical_min,
                "critical_max": sensor.critical_max,
            }
            for sensor in sensors
        ])
        features = FeaturePipeline(sensors_df=sensors_df).transform(telemetry_df)
        component_types = {str(component.id): component.component_type for component in components}
        predictions: list[Prediction] = []

        for component in components:
            component_id = str(component.id)
            component_features = features[features["component_id"] == component_id]
            if component_features.empty:
                continue
            predictions.extend(self._predict_component(
                db,
                component_id=component.id,
                asset_id=asset.id,
                component_type=component_types.get(component_id),
                features=component_features,
            ))

        db.flush()
        self.readiness_service.evaluate_asset(db, asset_id)
        db.commit()
        return predictions

    def _predict_component(
        self,
        db: Session,
        *,
        component_id: uuid.UUID,
        asset_id: uuid.UUID,
        component_type: str | None,
        features: pd.DataFrame,
    ) -> list[Prediction]:
        result: list[Prediction] = []
        predicted_at = datetime.now(timezone.utc)

        rul = RULInference(registry=self.registry).predict(features, str(component_id), str(asset_id))
        if rul.predicted_rul_hours is not None:
            result.append(self.prediction_repo.create(db, {
                "asset_id": asset_id,
                "component_id": component_id,
                "prediction_type": "RUL",
                "rul_estimate": rul.predicted_rul_hours,
                "rul_lower": rul.lower_bound,
                "rul_upper": rul.upper_bound,
                "confidence": rul.confidence,
                "observation_count": rul.n_history_rows,
                "feature_window_hours": float(rul.n_history_rows),
                "predicted_at": predicted_at,
            }))

        failure = FailureInference(horizon="24h", registry=self.registry).predict(
            features, str(component_id), str(asset_id)
        )
        if failure.failure_probability is not None:
            result.append(self.prediction_repo.create(db, {
                "asset_id": asset_id,
                "component_id": component_id,
                "prediction_type": "FAILURE_RISK",
                "failure_probability": failure.failure_probability,
                "confidence": failure.confidence,
                "observation_count": failure.n_history_rows,
                "feature_window_hours": float(failure.n_history_rows),
                "predicted_at": predicted_at,
            }))

        anomaly = AnomalyInference(component_type=component_type, registry=self.registry).predict(
            features, str(component_id), str(asset_id)
        )
        if anomaly.anomaly_score is not None:
            result.append(self.prediction_repo.create(db, {
                "asset_id": asset_id,
                "component_id": component_id,
                "prediction_type": "ANOMALY",
                "anomaly_score": anomaly.anomaly_score,
                "confidence": anomaly.confidence,
                "observation_count": anomaly.n_history_rows,
                "feature_window_hours": float(anomaly.n_history_rows),
                "predicted_at": predicted_at,
            }))
        return result