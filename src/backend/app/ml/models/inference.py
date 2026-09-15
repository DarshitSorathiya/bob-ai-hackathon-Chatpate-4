"""
Inference interfaces for the backend API — Phase 6.

Three inference classes, one per task:
  RULInference          — predict remaining useful life
  FailureInference      — predict failure probability for a horizon
  AnomalyInference      — score anomaly + attribute top contributing features

Design contract
---------------
All predict() methods:
  - Accept a raw feature DataFrame (already processed by FeaturePipeline)
    for a SINGLE component or asset.
  - Run a leakage check before inference.
  - Return a typed result dataclass.
  - Return a null/safe result when data is insufficient:
      rul:     predicted_rul_hours=None, confidence=0.0
      failure: failure_probability=None, confidence=0.0
      anomaly: anomaly_score=None, is_anomaly=None, confidence=0.0
  - Attach prediction timestamp.
  - Never raise exceptions on bad input — return null result instead.

Loading
-------
Each class lazily loads the model from the registry on first call
(or on explicit load()). The registry is shared across all three classes.

Thread safety
-------------
Model loading is idempotent and joblib files are read-only after registration.
Production deployments should pre-load models at startup.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.ml.models.leakage import LeakageGuard
from app.ml.models.registry import ModelRegistry
from app.ml.training.anomaly import (
    AnomalyPredictionResult,
    _normalise_scores,
    _top_contributing_features,
    MIN_HISTORY_ROWS as ANOMALY_MIN_ROWS,
)
from app.ml.training.failure import (
    FailurePredictionResult,
    MIN_HISTORY_ROWS as FAILURE_MIN_ROWS,
    OPERATIONAL_THRESHOLDS,
)
from app.ml.training.rul import (
    RULPredictionResult,
    MIN_HISTORY_ROWS as RUL_MIN_ROWS,
    RUL_CAP,
    _rf_prediction_interval,
    _gb_prediction_interval,
)
from app.ml.training.utils import get_numeric_feature_cols


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── RUL Inference ────────────────────────────────────────────────────────────


class RULInference:
    """Inference interface for RUL estimation.

    Parameters
    ----------
    tag:
        Model tag to load (e.g. "rul-xgboost-v1").
        If None, loads the first available "rul-*" tag.
    registry:
        ModelRegistry to load from.
    """

    def __init__(
        self,
        tag: str | None = None,
        registry: ModelRegistry | None = None,
    ) -> None:
        self.registry = registry or ModelRegistry()
        self._tag = tag
        self._bundle: dict | None = None
        self._record = None
        self._feature_names: list[str] | None = None

    def load(self) -> "RULInference":
        """Explicitly load the model. Called lazily on first predict()."""
        tag = self._resolve_tag("rul")
        estimator, record = self.registry.load(tag)
        self._bundle = estimator   # dict: model, imputer, pi_lo, pi_hi
        self._record = record
        self._feature_names = record.feature_names
        self._tag = tag
        return self

    def predict(
        self,
        features_df: pd.DataFrame,
        component_id: str,
        asset_id: str,
    ) -> RULPredictionResult:
        """Predict RUL for a single component.

        Parameters
        ----------
        features_df:
            Feature rows for this component (output of FeaturePipeline.transform).
            May contain multiple time steps; prediction is made on the LATEST row.
        component_id, asset_id:
            Identifiers for the result metadata.
        """
        if self._bundle is None:
            try:
                self.load()
            except Exception as e:
                return self._null_result(component_id, asset_id, str(e))

        n_rows = len(features_df)
        if n_rows < RUL_MIN_ROWS:
            return self._null_result(
                component_id, asset_id,
                f"insufficient_history: {n_rows} rows (need {RUL_MIN_ROWS})",
            )

        X = self._prepare_X(features_df)
        if X is None:
            return self._null_result(component_id, asset_id, "all_features_nan")

        try:
            LeakageGuard.check(pd.DataFrame(X.reshape(1, -1),
                                             columns=self._feature_names), task="rul")
        except Exception as e:
            return self._null_result(component_id, asset_id, f"leakage_guard: {e}")

        model = self._bundle["model"]
        imputer = self._bundle["imputer"]
        pi_lo = self._bundle.get("pi_lo")
        pi_hi = self._bundle.get("pi_hi")

        X_imp = imputer.transform(X.reshape(1, -1))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rul_pred = float(np.clip(model.predict(X_imp)[0], 0.0, RUL_CAP))

        # Prediction interval
        lower, upper = self._compute_pi(model, pi_lo, pi_hi, X_imp)
        lower = float(np.clip(lower, 0.0, RUL_CAP))
        upper = float(np.clip(upper, 0.0, RUL_CAP))

        # Confidence: higher when history is longer and PI is narrow
        pi_width_fraction = (upper - lower) / (RUL_CAP + 1e-9)
        history_factor = min(1.0, n_rows / 72.0)   # saturates at 72h of history
        confidence = float(history_factor * max(0.1, 1.0 - pi_width_fraction))

        return RULPredictionResult(
            component_id=component_id,
            asset_id=asset_id,
            predicted_rul_hours=rul_pred,
            lower_bound=lower,
            upper_bound=upper,
            confidence=round(confidence, 3),
            feature_version=self._record.feature_version,
            model_tag=self._tag,
            predicted_at=_now_iso(),
            n_history_rows=n_rows,
        )

    def _prepare_X(self, features_df: pd.DataFrame) -> np.ndarray | None:
        """Select feature columns from the latest row of features_df."""
        available = [c for c in self._feature_names if c in features_df.columns]
        if not available:
            return None
        # Use most recent row (last by recorded_at if available)
        if "recorded_at" in features_df.columns:
            row = features_df.sort_values("recorded_at").iloc[[-1]]
        else:
            row = features_df.iloc[[-1]]
        X = np.zeros((1, len(self._feature_names)))
        for i, col in enumerate(self._feature_names):
            if col in row.columns:
                X[0, i] = float(row[col].values[0]) if not pd.isna(row[col].values[0]) else np.nan
            else:
                X[0, i] = np.nan
        if np.all(np.isnan(X)):
            return None
        return X.flatten()

    def _compute_pi(self, model, pi_lo, pi_hi, X_imp) -> tuple[float, float]:
        algo = type(model).__name__
        if pi_lo is not None and pi_hi is not None:
            lo = float(np.clip(pi_lo.predict(X_imp)[0], 0.0, RUL_CAP))
            hi = float(np.clip(pi_hi.predict(X_imp)[0], 0.0, RUL_CAP))
            return lo, hi
        if algo == "RandomForestRegressor":
            lo_arr, hi_arr = _rf_prediction_interval(model, X_imp)
            return float(lo_arr[0]), float(hi_arr[0])
        # Fallback: ±20% of prediction
        pred = float(np.clip(model.predict(X_imp)[0], 0.0, RUL_CAP))
        return pred * 0.8, pred * 1.2

    def _null_result(self, component_id: str, asset_id: str, reason: str) -> RULPredictionResult:
        tag = self._tag or "not_loaded"
        fv = self._record.feature_version if self._record else "unknown"
        return RULPredictionResult(
            component_id=component_id, asset_id=asset_id,
            predicted_rul_hours=None, lower_bound=None, upper_bound=None,
            confidence=0.0, feature_version=fv, model_tag=tag,
            predicted_at=_now_iso(), n_history_rows=0, null_reason=reason,
        )

    def _resolve_tag(self, prefix: str) -> str:
        if self._tag:
            return self._tag
        tags = [t for t in self.registry.list_tags() if t.startswith(prefix)]
        if not tags:
            raise FileNotFoundError(
                f"No model with tag prefix '{prefix}' found in registry. "
                "Run the training pipeline first."
            )
        # Prefer the most recently modified (last alphabetically for version suffixes)
        return sorted(tags)[-1]


# ─── Failure Inference ────────────────────────────────────────────────────────


class FailureInference:
    """Inference interface for failure probability prediction.

    Parameters
    ----------
    horizon:
        One of '24h', '72h', 'mission_window'.
    tag:
        Explicit model tag. If None, resolved from registry.
    """

    def __init__(
        self,
        horizon: str = "24h",
        tag: str | None = None,
        registry: ModelRegistry | None = None,
        operational_threshold: float = 0.5,
    ) -> None:
        self.horizon = horizon
        self.registry = registry or ModelRegistry()
        self._tag = tag
        self._bundle: dict | None = None
        self._record = None
        self._feature_names: list[str] | None = None
        self.operational_threshold = operational_threshold

    def load(self) -> "FailureInference":
        tag = self._resolve_tag()
        estimator, record = self.registry.load(tag)
        self._bundle = estimator
        self._record = record
        self._feature_names = record.feature_names
        self._tag = tag
        return self

    def predict(
        self,
        features_df: pd.DataFrame,
        component_id: str,
        asset_id: str,
    ) -> FailurePredictionResult:
        """Predict failure probability for a single component."""
        if self._bundle is None:
            try:
                self.load()
            except Exception as e:
                return self._null_result(component_id, asset_id, str(e))

        n_rows = len(features_df)
        if n_rows < FAILURE_MIN_ROWS:
            return self._null_result(
                component_id, asset_id,
                f"insufficient_history: {n_rows} rows",
            )

        X = self._prepare_X(features_df)
        if X is None:
            return self._null_result(component_id, asset_id, "all_features_nan")

        try:
            LeakageGuard.check(
                pd.DataFrame(X.reshape(1, -1), columns=self._feature_names),
                task="failure",
            )
        except Exception as e:
            return self._null_result(component_id, asset_id, f"leakage_guard: {e}")

        model = self._bundle["model"]
        imputer = self._bundle["imputer"]
        X_imp = imputer.transform(X.reshape(1, -1))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            prob = float(np.clip(model.predict_proba(X_imp)[0, 1], 0.0, 1.0))

        # Confidence: higher when history is longer
        confidence = float(min(1.0, n_rows / 48.0))

        return FailurePredictionResult(
            component_id=component_id,
            asset_id=asset_id,
            horizon=self.horizon,
            failure_probability=prob,
            confidence=round(confidence, 3),
            feature_version=self._record.feature_version,
            model_tag=self._tag,
            predicted_at=_now_iso(),
            n_history_rows=n_rows,
            operational_threshold=self.operational_threshold,
            alert=prob >= self.operational_threshold,
        )

    def _prepare_X(self, features_df: pd.DataFrame) -> np.ndarray | None:
        if "recorded_at" in features_df.columns:
            row = features_df.sort_values("recorded_at").iloc[[-1]]
        else:
            row = features_df.iloc[[-1]]
        X = np.zeros((1, len(self._feature_names)))
        for i, col in enumerate(self._feature_names):
            if col in row.columns:
                X[0, i] = float(row[col].values[0]) if not pd.isna(row[col].values[0]) else np.nan
            else:
                X[0, i] = np.nan
        if np.all(np.isnan(X)):
            return None
        return X.flatten()

    def _null_result(self, component_id: str, asset_id: str, reason: str) -> FailurePredictionResult:
        tag = self._tag or "not_loaded"
        fv = self._record.feature_version if self._record else "unknown"
        return FailurePredictionResult(
            component_id=component_id, asset_id=asset_id,
            horizon=self.horizon, failure_probability=None,
            confidence=0.0, feature_version=fv, model_tag=tag,
            predicted_at=_now_iso(), n_history_rows=0,
            null_reason=reason, operational_threshold=self.operational_threshold,
            alert=False,
        )

    def _resolve_tag(self) -> str:
        if self._tag:
            return self._tag
        prefix = f"failure-{self.horizon}"
        tags = [t for t in self.registry.list_tags() if t.startswith(prefix)]
        if not tags:
            raise FileNotFoundError(
                f"No model with tag prefix '{prefix}' found in registry."
            )
        return sorted(tags)[-1]


# ─── Anomaly Inference ────────────────────────────────────────────────────────


class AnomalyInference:
    """Inference interface for anomaly detection.

    Parameters
    ----------
    component_type:
        Component type string matching the training scope (e.g. "ENGINE_CORE").
        If None, uses the "global" fallback.
    tag:
        Explicit model tag. If None, resolved from registry.
    """

    def __init__(
        self,
        component_type: str | None = None,
        tag: str | None = None,
        registry: ModelRegistry | None = None,
        anomaly_threshold_percentile: float = 0.95,
    ) -> None:
        self.component_type = component_type or "global"
        self.registry = registry or ModelRegistry()
        self._tag = tag
        self._bundle: dict | None = None
        self._record = None
        self._feature_names: list[str] | None = None
        self.anomaly_threshold_percentile = anomaly_threshold_percentile

    def load(self) -> "AnomalyInference":
        tag = self._resolve_tag()
        bundle, record = self.registry.load(tag)
        self._bundle = bundle
        self._record = record
        self._feature_names = record.feature_names
        self._tag = tag
        return self

    def predict(
        self,
        features_df: pd.DataFrame,
        component_id: str,
        asset_id: str,
    ) -> AnomalyPredictionResult:
        """Score anomaly for a single component using the latest feature row."""
        if self._bundle is None:
            try:
                self.load()
            except Exception as e:
                return self._null_result(component_id, asset_id, str(e))

        n_rows = len(features_df)
        if n_rows < ANOMALY_MIN_ROWS:
            return self._null_result(
                component_id, asset_id,
                f"insufficient_history: {n_rows} rows",
            )

        X = self._prepare_X(features_df)
        if X is None:
            return self._null_result(component_id, asset_id, "all_features_nan")

        # Leakage check
        try:
            LeakageGuard.check(
                pd.DataFrame(X.reshape(1, -1), columns=self._feature_names),
                task="anomaly",
            )
        except Exception as e:
            return self._null_result(component_id, asset_id, f"leakage_guard: {e}")

        model = self._bundle["model"]
        imputer = self._bundle["imputer"]
        train_mean: np.ndarray = self._bundle["train_mean"]
        train_std: np.ndarray = self._bundle["train_std"]

        X_imp = imputer.transform(X.reshape(1, -1))

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                raw_score = model.decision_function(X_imp)[0]
        except AttributeError:
            try:
                raw_score = model.score_samples(X_imp)[0]
            except Exception as e:
                return self._null_result(component_id, asset_id, f"score_failed: {e}")

        # Normalise to [0, 1]; we use a fixed reference range from training
        # decision_function values are typically in [-0.5, 0.5]; negate so higher = worse
        anomaly_score = float(np.clip(0.5 - raw_score, 0.0, 1.0))
        is_anomaly = anomaly_score >= self.anomaly_threshold_percentile

        # Attribution: z-scores
        x_flat = X_imp.flatten()
        top_feats = _top_contributing_features(
            x_flat, train_mean, train_std, self._feature_names, top_n=5
        )

        confidence = float(min(1.0, n_rows / 48.0))

        return AnomalyPredictionResult(
            component_id=component_id,
            asset_id=asset_id,
            anomaly_score=round(anomaly_score, 4),
            is_anomaly=bool(is_anomaly),
            confidence=round(confidence, 3),
            top_contributing_features=top_feats,
            feature_version=self._record.feature_version,
            model_tag=self._tag,
            predicted_at=_now_iso(),
            n_history_rows=n_rows,
        )

    def _prepare_X(self, features_df: pd.DataFrame) -> np.ndarray | None:
        if "recorded_at" in features_df.columns:
            row = features_df.sort_values("recorded_at").iloc[[-1]]
        else:
            row = features_df.iloc[[-1]]
        X = np.zeros((1, len(self._feature_names)))
        for i, col in enumerate(self._feature_names):
            if col in row.columns:
                X[0, i] = float(row[col].values[0]) if not pd.isna(row[col].values[0]) else np.nan
            else:
                X[0, i] = np.nan
        if np.all(np.isnan(X)):
            return None
        return X.flatten()

    def _null_result(
        self,
        component_id: str,
        asset_id: str,
        reason: str,
    ) -> AnomalyPredictionResult:
        tag = self._tag or "not_loaded"
        fv = self._record.feature_version if self._record else "unknown"
        return AnomalyPredictionResult(
            component_id=component_id, asset_id=asset_id,
            anomaly_score=None, is_anomaly=None,
            confidence=0.0, top_contributing_features=[],
            feature_version=fv, model_tag=tag,
            predicted_at=_now_iso(), n_history_rows=0, null_reason=reason,
        )

    def _resolve_tag(self) -> str:
        if self._tag:
            return self._tag
        prefix = f"anomaly-{self.component_type.lower().replace(' ', '_')}"
        tags = [t for t in self.registry.list_tags() if t.startswith(prefix)]
        if not tags:
            # Fall back to any anomaly model
            tags = [t for t in self.registry.list_tags() if t.startswith("anomaly-")]
        if not tags:
            raise FileNotFoundError(
                f"No anomaly model found in registry for component_type "
                f"'{self.component_type}'."
            )
        return sorted(tags)[-1]
