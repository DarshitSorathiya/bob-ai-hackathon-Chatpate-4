"""
Anomaly detection — Phase 6.

Approaches evaluated
--------------------
1. IsolationForest            — robust, efficient, good on high-dim tabular
2. LocalOutlierFactor (LOF)   — density-based, captures local anomalies
3. EllipticEnvelope           — Mahalanobis-distance Gaussian assumption (baseline)

Scope: one model per component_type (not per individual asset) — avoids
overfitting while allowing type-specific normal behaviour.

Evaluation
----------
Anomaly detection is unsupervised at training time. Evaluation uses the
injected edge-case events from the simulator (data_quality_events + truth
knowledge of degraded assets):

  - Detection rate on known injected anomaly windows: fraction of injected
    fault windows that score above the anomaly threshold.
  - False positive rate on HEALTHY windows (true_health > 0.9) from truth.
  - AUCROC where we treat "injected edge case" windows as positive class.

Contributing sensor attribution
---------------------------------
For an anomalous row, we identify the top contributing features by:
  Feature contribution = |x_i - mu_i| / sigma_i  (z-score based)
This is robust, fast, and interpretable. The top-N sensors are reported
alongside the anomaly score.

Training granularity
--------------------
Option A: global model across all component types
Option B: one model per component_type

We use Option B (per-component-type) because degradation patterns differ
significantly across engine core, gearbox, rotor, etc.

Safe null output
----------------
predict() returns score=None and is_anomaly=None when fewer than
MIN_HISTORY_ROWS rows are available.
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.covariance import EllipticEnvelope
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

from app.ml.models.registry import ModelRegistry
from app.ml.training.utils import (
    feature_importance_dict,
    get_numeric_feature_cols,
    impute,
    leakage_pass_result,
)

MIN_HISTORY_ROWS: int = 6

# Contamination assumption: expected fraction of anomalies in training data.
# Since training uses all simulator output (including injected faults), we
# set this conservatively. Can be tuned per profile.
DEFAULT_CONTAMINATION: float = 0.05


# ─── Result containers ────────────────────────────────────────────────────────


@dataclass
class AnomalyPredictionResult:
    """Single-row anomaly prediction."""

    component_id: str
    asset_id: str
    anomaly_score: float | None         # higher = more anomalous (range -1..1 for IF)
    is_anomaly: bool | None             # None = insufficient data
    confidence: float                   # 0.0 = unreliable
    top_contributing_features: list[tuple[str, float]]  # [(feat_name, z_score), ...]
    feature_version: str
    model_tag: str
    predicted_at: str
    n_history_rows: int
    null_reason: str | None = None


@dataclass
class AnomalyEvaluationResult:
    """Evaluation result for one component type × one algorithm."""

    tag: str
    component_type: str
    algorithm: str
    n_train: int
    contamination: float
    # Evaluation against edge-case / degraded windows
    detection_rate: float        # fraction of anomalous windows correctly flagged
    false_positive_rate: float   # fraction of healthy windows incorrectly flagged
    roc_auc: float               # if labels available; 0.5 = random
    attribution_coverage: float  # fraction of anomalous windows with attribution
    training_time_s: float
    n_features: int


# ─── Baselines ────────────────────────────────────────────────────────────────


def _build_candidates(seed: int, contamination: float) -> dict[str, object]:
    return {
        "isolation_forest": IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=seed,
            n_jobs=-1,
        ),
        "local_outlier_factor": LocalOutlierFactor(
            n_neighbors=20,
            contamination=contamination,
            novelty=True,   # enables predict() on new data
        ),
        "elliptic_envelope": EllipticEnvelope(
            contamination=contamination,
            random_state=seed,
            support_fraction=0.9,
        ),
    }


# ─── Score normalisation ─────────────────────────────────────────────────────


def _normalise_scores(raw_scores: np.ndarray) -> np.ndarray:
    """Map raw anomaly scores to [0, 1] where 1 = most anomalous.

    IsolationForest returns decision_function scores in roughly [-0.5, 0.5]
    where lower = more anomalous. We negate and min-max normalise.
    """
    s = -raw_scores  # negate so higher = more anomalous
    lo, hi = s.min(), s.max()
    if hi > lo:
        return (s - lo) / (hi - lo)
    return np.zeros_like(s)


# ─── Attribution ──────────────────────────────────────────────────────────────


def _top_contributing_features(
    row: np.ndarray,
    mean: np.ndarray,
    std: np.ndarray,
    feature_names: list[str],
    top_n: int = 5,
) -> list[tuple[str, float]]:
    """Return top-N features by absolute z-score for a single anomalous row."""
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(std > 1e-9, np.abs(row - mean) / std, 0.0)
    top_idx = np.argsort(z)[::-1][:top_n]
    return [(feature_names[i], float(z[i])) for i in top_idx if z[i] > 0]


# ─── Per-type trainer ─────────────────────────────────────────────────────────


class AnomalyTrainer:
    """Train anomaly detectors per component type.

    Parameters
    ----------
    seed:
        Global random seed.
    registry:
        ModelRegistry instance.
    contamination:
        Assumed fraction of anomalies in training data.
    component_type_col:
        Column name in features_df that identifies the component type.
        Must be joinable from the components observable table.
    """

    def __init__(
        self,
        seed: int = 42,
        registry: ModelRegistry | None = None,
        contamination: float = DEFAULT_CONTAMINATION,
        component_type_col: str = "component_type",
    ) -> None:
        self.seed = seed
        self.registry = registry or ModelRegistry()
        self.contamination = contamination
        self.component_type_col = component_type_col

    def train(
        self,
        features_df: pd.DataFrame,
        components_df: pd.DataFrame,
        edge_case_tags: dict[str, list[str]] | None = None,
        truth_health_df: pd.DataFrame | None = None,
        tag_prefix: str = "anomaly",
    ) -> dict[str, tuple[str, AnomalyEvaluationResult]]:
        """Train per-component-type anomaly detectors.

        Parameters
        ----------
        features_df:
            Feature DataFrame (no truth columns).
        components_df:
            observable["components"] — provides component_type mapping.
        edge_case_tags:
            Dict asset_id → list of edge case tag strings (from SimulationResult).
            Used to label anomalous windows for evaluation.
        truth_health_df:
            truth["component_health_trajectories"] — optional, used to identify
            healthy windows (true_health > 0.9) for FPR evaluation.
        tag_prefix:
            Prefix for artifact tags.

        Returns
        -------
        dict mapping component_type → (selected_tag, evaluation_result)
        """
        # Join component_type onto features
        feats = self._attach_component_type(features_df, components_df)

        # Identify anomalous and healthy windows using edge cases + truth
        anomalous_asset_ids: set[str] = set()
        if edge_case_tags:
            # Any asset with injected faults is "anomalous"
            anomalous_asset_ids = {
                a for a, tags in edge_case_tags.items()
                if tags  # any tag counts
            }

        healthy_component_ids: set[str] = set()
        if truth_health_df is not None and not truth_health_df.empty:
            healthy = truth_health_df[truth_health_df["true_health"] > 0.9]
            healthy_component_ids = set(healthy["component_id"].unique())

        results: dict[str, tuple[str, AnomalyEvaluationResult]] = {}

        component_types = feats[self.component_type_col].dropna().unique().tolist()
        if not component_types:
            # Fall back to training a global model
            component_types = ["global"]

        for ctype in component_types:
            if ctype == "global":
                type_df = feats
            else:
                type_df = feats[feats[self.component_type_col] == ctype]

            if len(type_df) < 30:
                continue

            result = self._train_one_type(
                component_type=ctype,
                type_df=type_df,
                anomalous_asset_ids=anomalous_asset_ids,
                healthy_component_ids=healthy_component_ids,
                tag_prefix=tag_prefix,
            )
            if result is not None:
                results[ctype] = result

        return results

    def _train_one_type(
        self,
        component_type: str,
        type_df: pd.DataFrame,
        anomalous_asset_ids: set[str],
        healthy_component_ids: set[str],
        tag_prefix: str,
    ) -> tuple[str, AnomalyEvaluationResult] | None:
        """Train and evaluate candidates for one component type."""
        feat_cols = get_numeric_feature_cols(type_df)
        # Also remove component_type if it crept in
        feat_cols = [c for c in feat_cols if c != self.component_type_col]
        if not feat_cols:
            return None

        X = type_df[feat_cols].copy()
        # Impute NaN with median (fit on full type dataset — unsupervised)
        X_imp, _, _, imputer = impute(X)
        X_np = X_imp.values

        # Compute training set mean/std for attribution
        train_mean = X_np.mean(axis=0)
        train_std = X_np.std(axis=0)
        # Avoid zero std
        train_std = np.where(train_std < 1e-9, 1.0, train_std)

        candidates = _build_candidates(self.seed, self.contamination)
        best_algo: str | None = None
        best_score: float = -np.inf
        best_eval: AnomalyEvaluationResult | None = None
        best_estimator = None

        for algo_name, estimator in candidates.items():
            ev = self._evaluate_candidate(
                algo_name=algo_name,
                estimator=estimator,
                component_type=component_type,
                type_df=type_df,
                X_np=X_np,
                feat_cols=feat_cols,
                anomalous_asset_ids=anomalous_asset_ids,
                healthy_component_ids=healthy_component_ids,
                tag_prefix=tag_prefix,
            )
            if ev is None:
                continue
            # Select by detection rate; break ties by false positive rate (lower is better)
            score = ev.detection_rate - 0.5 * ev.false_positive_rate
            if score > best_score:
                best_score = score
                best_algo = algo_name
                best_eval = ev
                best_estimator = estimator  # already fit inside _evaluate_candidate

        if best_algo is None or best_eval is None:
            return None

        leakage_result = leakage_pass_result(feat_cols)
        selected_tag = f"{tag_prefix}-{component_type.lower().replace(' ', '_')}-{best_algo}-v1"

        training_metadata = {
            "seed": self.seed,
            "component_type": component_type,
            "algorithm": best_algo,
            "contamination": self.contamination,
            "feature_cols": feat_cols,
            "n_train": len(X_np),
            "train_mean": train_mean.tolist(),
            "train_std": train_std.tolist(),
        }

        self.registry.register(
            task="anomaly",
            tag=selected_tag,
            estimator={
                "model": best_estimator,
                "imputer": imputer,
                "train_mean": train_mean,
                "train_std": train_std,
            },
            feature_names=feat_cols,
            training_metadata=training_metadata,
            evaluation_metadata={k: getattr(best_eval, k)
                                  for k in best_eval.__dataclass_fields__},
            leakage_result=leakage_result,
        )

        return selected_tag, best_eval

    def _evaluate_candidate(
        self,
        algo_name: str,
        estimator: object,
        component_type: str,
        type_df: pd.DataFrame,
        X_np: np.ndarray,
        feat_cols: list[str],
        anomalous_asset_ids: set[str],
        healthy_component_ids: set[str],
        tag_prefix: str,
    ) -> AnomalyEvaluationResult | None:
        t0 = time.perf_counter()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                estimator.fit(X_np)
        except Exception:
            return None

        train_time = time.perf_counter() - t0

        # Get raw scores (decision_function / score_samples)
        try:
            raw_scores = estimator.decision_function(X_np)
        except AttributeError:
            try:
                raw_scores = estimator.score_samples(X_np)
            except Exception:
                return None

        norm_scores = _normalise_scores(raw_scores)
        # Anomaly label: score in top contamination fraction
        threshold = np.percentile(norm_scores, (1 - self.contamination) * 100)
        predicted_anomaly = norm_scores >= threshold

        # Evaluate detection rate vs injected anomaly windows
        if "asset_id" in type_df.columns and anomalous_asset_ids:
            anom_mask = type_df["asset_id"].isin(anomalous_asset_ids).values
            n_anom = int(anom_mask.sum())
            detection_rate = (
                float((predicted_anomaly & anom_mask).sum() / n_anom)
                if n_anom > 0 else 0.0
            )
        else:
            detection_rate = 0.0

        # False positive rate on healthy windows
        if "component_id" in type_df.columns and healthy_component_ids:
            healthy_mask = type_df["component_id"].isin(healthy_component_ids).values
            n_healthy = int(healthy_mask.sum())
            fpr = (
                float((predicted_anomaly & healthy_mask).sum() / n_healthy)
                if n_healthy > 0 else 0.0
            )
        else:
            fpr = float(predicted_anomaly.mean())

        # ROC-AUC if we have labels
        roc = 0.5
        if "asset_id" in type_df.columns and anomalous_asset_ids and n_anom > 0:
            from sklearn.metrics import roc_auc_score
            anom_labels = anom_mask.astype(int)
            if len(np.unique(anom_labels)) > 1:
                try:
                    roc = float(roc_auc_score(anom_labels, norm_scores))
                except Exception:
                    pass

        # Attribution coverage: what fraction of anomalous rows get attribution?
        n_anom_pred = int(predicted_anomaly.sum())
        attribution_coverage = 1.0 if n_anom_pred > 0 else 0.0  # z-score always works

        return AnomalyEvaluationResult(
            tag=f"{tag_prefix}-{component_type.lower()}-{algo_name}",
            component_type=component_type,
            algorithm=algo_name,
            n_train=len(X_np),
            contamination=self.contamination,
            detection_rate=detection_rate,
            false_positive_rate=fpr,
            roc_auc=roc,
            attribution_coverage=attribution_coverage,
            training_time_s=round(train_time, 3),
            n_features=len(feat_cols),
        )

    @staticmethod
    def _attach_component_type(
        features_df: pd.DataFrame,
        components_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Join component_type from components table onto features."""
        if components_df.empty or "component_type" not in components_df.columns:
            feats = features_df.copy()
            feats["component_type"] = "global"
            return feats
        mapping = components_df[["component_id", "component_type"]].drop_duplicates()
        return features_df.merge(mapping, on="component_id", how="left")


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _ev_to_dict(ev: AnomalyEvaluationResult) -> dict[str, Any]:
    from dataclasses import asdict
    return asdict(ev)
