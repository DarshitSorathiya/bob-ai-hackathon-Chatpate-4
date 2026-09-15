"""
Failure probability prediction — Phase 6.

Baselines evaluated
-------------------
1. LogisticRegression (L2)         — linear baseline, well-calibrated
2. RandomForestClassifier          — ensemble baseline, OOB probabilities
3. GradientBoostingClassifier      — strong baseline
4. XGBClassifier                   — often best on tabular; scale_pos_weight for imbalance

Horizons
--------
Three binary classification targets are supported:
  failure_within_24h    — failure in the next 24 hours
  failure_within_72h    — failure in the next 72 hours
  failure_within_window — failure within the configured mission window

Imbalance handling
------------------
Failure events are rare. All classifiers use class_weight='balanced' or
scale_pos_weight (XGB). No oversampling is applied by default to avoid
inflating reported metrics.

Evaluation
----------
  Precision, Recall, F1 (threshold 0.5 and optimal threshold from PR curve)
  PR-AUC (average precision) — primary metric for imbalanced classification
  ROC-AUC — secondary
  ECE (Expected Calibration Error) — 10-bin calibration
  Brier score
  Confusion matrix at operational thresholds (0.3, 0.5, 0.7)

Calibration
-----------
Post-hoc Platt scaling (CalibratedClassifierCV, sigmoid method) applied to the
selected model. ECE computed before and after calibration.

Safe null output
----------------
predict() returns probability=None and confidence=0.0 if fewer than
MIN_HISTORY_ROWS rows are available or if all features are NaN.
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from app.ml.features.split import AssetTemporalSplitter
from app.ml.models.registry import ModelRegistry
from app.ml.training.utils import (
    build_X_y,
    feature_importance_dict,
    get_numeric_feature_cols,
    impute,
    leakage_pass_result,
)

MIN_HISTORY_ROWS: int = 6

# Horizons to train — (label column, human label)
FAILURE_HORIZONS: list[tuple[str, str]] = [
    ("failure_within_24h", "24h"),
    ("failure_within_72h", "72h"),
    ("failure_within_window", "mission_window"),
]

# Operational thresholds to report metrics at
OPERATIONAL_THRESHOLDS: list[float] = [0.3, 0.5, 0.7]


# ─── Result containers ────────────────────────────────────────────────────────


@dataclass
class FailurePredictionResult:
    """Single-row prediction from FailureInference."""

    component_id: str
    asset_id: str
    horizon: str                             # "24h" | "72h" | "mission_window"
    failure_probability: float | None        # None = insufficient data
    confidence: float                        # 0.0 = unreliable
    feature_version: str
    model_tag: str
    predicted_at: str
    n_history_rows: int
    null_reason: str | None = None
    operational_threshold: float = 0.5
    alert: bool = False                      # True if probability >= threshold


@dataclass
class FailureEvaluationResult:
    """Evaluation metrics for one horizon × one algorithm."""

    tag: str
    horizon: str
    algorithm: str
    n_train: int
    n_val: int
    n_test: int
    positive_rate_train: float
    positive_rate_test: float
    # Core metrics
    pr_auc: float           # primary
    roc_auc: float
    brier_score: float
    # At optimal threshold from PR curve
    optimal_threshold: float
    precision_at_optimal: float
    recall_at_optimal: float
    f1_at_optimal: float
    # At fixed thresholds
    metrics_at_thresholds: dict[str, dict[str, float]]
    # Calibration
    ece_before_calibration: float
    ece_after_calibration: float
    training_time_s: float
    feature_importance: dict[str, float] = field(default_factory=dict)


# ─── Baselines ────────────────────────────────────────────────────────────────


def _build_candidates(seed: int, pos_weight: float) -> dict[str, object]:
    return {
        "logistic": Pipeline([
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(
                C=1.0, max_iter=500, class_weight="balanced",
                random_state=seed, solver="lbfgs",
            )),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=10, min_samples_leaf=5,
            class_weight="balanced", n_jobs=-1, random_state=seed,
            oob_score=True,
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, min_samples_leaf=5, random_state=seed,
        ),
        "xgboost": XGBClassifier(
            n_estimators=400, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
            scale_pos_weight=max(1.0, pos_weight),
            random_state=seed, eval_metric="aucpr", verbosity=0,
            use_label_encoder=False,
        ),
    }


# ─── Metrics ──────────────────────────────────────────────────────────────────


def _ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (10-bin, weighted by bin size)."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() == 0:
            continue
        bin_acc = float(y_true[mask].mean())
        bin_conf = float(y_prob[mask].mean())
        ece += (mask.sum() / n) * abs(bin_acc - bin_conf)
    return float(ece)


def _optimal_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Threshold that maximises F1 on the precision-recall curve."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    # Avoid division by zero
    with np.errstate(invalid="ignore", divide="ignore"):
        denom = precision + recall
        f1_scores = np.where(denom > 0, 2 * precision * recall / denom, 0.0)
    # thresholds has one fewer element than precision/recall
    if len(thresholds) == 0:
        return 0.5
    best_idx = int(np.argmax(np.nan_to_num(f1_scores[:-1], nan=0.0)))
    return float(thresholds[best_idx])


def _metrics_at_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float,
) -> dict[str, float]:
    y_pred = (y_prob >= threshold).astype(int)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "false_negative_rate": fn / (fn + tp) if (fn + tp) > 0 else 0.0,
    }


# ─── Main trainer ─────────────────────────────────────────────────────────────


class FailureTrainer:
    """Train and compare failure probability models for all horizons.

    Parameters
    ----------
    seed:
        Global random seed.
    registry:
        ModelRegistry instance for persisting artifacts.
    horizons:
        List of (label_col, horizon_name) pairs to train. Default: all three.
    """

    def __init__(
        self,
        seed: int = 42,
        registry: ModelRegistry | None = None,
        horizons: list[tuple[str, str]] | None = None,
    ) -> None:
        self.seed = seed
        self.registry = registry or ModelRegistry()
        self.horizons = horizons or FAILURE_HORIZONS

    def train(
        self,
        features_df: pd.DataFrame,
        labels_df: pd.DataFrame,
        failure_events_df: pd.DataFrame | None = None,
        tag_prefix: str = "failure",
    ) -> dict[str, tuple[str, dict[str, FailureEvaluationResult]]]:
        """Train all candidates for each horizon. Register the best per horizon.

        Returns
        -------
        dict mapping horizon_name → (selected_tag, results_by_algo)
        """
        splitter = AssetTemporalSplitter(seed=self.seed)
        split = splitter.split(features_df, failure_events_df)
        train_f, val_f, test_f = split.apply(features_df)

        horizon_outputs: dict[str, tuple[str, dict[str, FailureEvaluationResult]]] = {}

        for label_col, horizon_name in self.horizons:
            result = self._train_horizon(
                label_col=label_col,
                horizon_name=horizon_name,
                train_f=train_f,
                val_f=val_f,
                test_f=test_f,
                labels_df=labels_df,
                split=split,
                tag_prefix=tag_prefix,
            )
            if result is not None:
                horizon_outputs[horizon_name] = result

        return horizon_outputs

    def _train_horizon(
        self,
        label_col: str,
        horizon_name: str,
        train_f: pd.DataFrame,
        val_f: pd.DataFrame,
        test_f: pd.DataFrame,
        labels_df: pd.DataFrame,
        split: object,
        tag_prefix: str,
    ) -> tuple[str, dict[str, FailureEvaluationResult]] | None:
        """Train all candidates for one horizon. Returns None if too few positives."""

        X_train, y_train, feat_cols = build_X_y(
            train_f, labels_df, label_col, "failure"
        )
        X_val, y_val, _ = build_X_y(
            val_f, labels_df, label_col, "failure", feature_cols=feat_cols
        )
        X_test, y_test, _ = build_X_y(
            test_f, labels_df, label_col, "failure", feature_cols=feat_cols
        )

        if len(X_train) < 30:
            return None  # not enough data

        y_tr = y_train.values.astype(int)
        y_v = y_val.values.astype(int)
        y_te = y_test.values.astype(int)

        n_pos = int(y_tr.sum())
        n_neg = int((y_tr == 0).sum())
        if n_pos < 5:
            return None  # too few positives to be meaningful

        pos_weight = n_neg / max(1, n_pos)

        X_tr, X_v, X_te, imputer = impute(X_train, X_val, X_test)

        candidates = _build_candidates(self.seed, pos_weight)
        results: dict[str, FailureEvaluationResult] = {}

        for algo_name, estimator in candidates.items():
            ev = self._evaluate_candidate(
                algo_name=algo_name,
                estimator=estimator,
                horizon_name=horizon_name,
                X_tr=X_tr.values, y_tr=y_tr,
                X_v=X_v.values, y_v=y_v,
                X_te=X_te.values, y_te=y_te,
                feat_cols=feat_cols,
                tag_prefix=tag_prefix,
            )
            if ev is not None:
                results[algo_name] = ev

        if not results:
            return None

        # Select by PR-AUC on validation set
        best_algo = max(results, key=lambda a: results[a].pr_auc)
        best_result = results[best_algo]
        best_estimator = candidates[best_algo]

        # Re-fit on train+val combined
        X_trainval = np.vstack([X_tr.values, X_v.values])
        y_trainval = np.concatenate([y_tr, y_v])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            best_estimator.fit(X_trainval, y_trainval)

        # Platt scaling calibration (sklearn 1.9+: use cv=5 on train subset)
        from sklearn.base import clone
        calibrated = CalibratedClassifierCV(
            clone(best_estimator), method="sigmoid", cv=5
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            calibrated.fit(X_tr.values, y_tr)

        leakage_result = leakage_pass_result(feat_cols)
        selected_tag = f"{tag_prefix}-{horizon_name}-{best_algo}-v1"

        training_metadata = {
            "seed": self.seed,
            "horizon": horizon_name,
            "label_col": label_col,
            "algorithm": best_algo,
            "split_metadata": split.split_metadata,
            "feature_cols": feat_cols,
            "imputer_strategy": "median",
            "positive_rate_train": float(y_tr.mean()),
            "pos_weight": float(pos_weight),
            "n_candidates_compared": len(candidates),
            "selection_criterion": "pr_auc_on_val",
        }

        self.registry.register(
            task="failure",
            tag=selected_tag,
            estimator={"model": calibrated, "imputer": imputer},
            feature_names=feat_cols,
            training_metadata=training_metadata,
            evaluation_metadata={
                "all_results": {k: _ev_to_dict(v) for k, v in results.items()},
                "selected": _ev_to_dict(best_result),
            },
            leakage_result=leakage_result,
            feature_importance=best_result.feature_importance,
        )

        return selected_tag, results

    def _evaluate_candidate(
        self,
        algo_name: str,
        estimator: object,
        horizon_name: str,
        X_tr: np.ndarray,
        y_tr: np.ndarray,
        X_v: np.ndarray,
        y_v: np.ndarray,
        X_te: np.ndarray,
        y_te: np.ndarray,
        feat_cols: list[str],
        tag_prefix: str,
    ) -> FailureEvaluationResult | None:
        t0 = time.perf_counter()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                estimator.fit(X_tr, y_tr)
        except Exception:
            return None

        train_time = time.perf_counter() - t0

        # Probabilities on test
        try:
            y_prob_te = estimator.predict_proba(X_te)[:, 1]
            y_prob_v = estimator.predict_proba(X_v)[:, 1]
        except AttributeError:
            return None

        # Guard: if test set has no positives, many metrics are undefined
        if y_te.sum() == 0 or y_v.sum() == 0:
            # Still record what we can
            pr_auc = float(average_precision_score(y_te, y_prob_te)) if y_te.sum() > 0 else 0.0
        else:
            pr_auc = float(average_precision_score(y_v, y_prob_v))

        try:
            roc = float(roc_auc_score(y_te, y_prob_te)) if len(np.unique(y_te)) > 1 else 0.5
        except Exception:
            roc = 0.5

        brier = float(brier_score_loss(y_te, y_prob_te))
        ece_before = _ece(y_te, y_prob_te)

        # Calibrate and re-measure ECE (sklearn 1.9+: cv=5)
        from sklearn.base import clone
        try:
            cal_eval = CalibratedClassifierCV(clone(estimator), method="sigmoid", cv=5)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cal_eval.fit(X_tr, y_tr)
            y_prob_cal = cal_eval.predict_proba(X_te)[:, 1]
            ece_after = _ece(y_te, y_prob_cal)
        except Exception:
            ece_after = ece_before

        opt_thresh = _optimal_threshold(y_te, y_prob_te) if y_te.sum() > 0 else 0.5

        # Metrics at optimal threshold
        opt_m = _metrics_at_threshold(y_te, y_prob_te, opt_thresh)

        # Metrics at operational thresholds
        thresh_metrics: dict[str, dict[str, float]] = {}
        for t in OPERATIONAL_THRESHOLDS:
            thresh_metrics[str(t)] = _metrics_at_threshold(y_te, y_prob_te, t)

        fi = feature_importance_dict(
            estimator if not isinstance(estimator, Pipeline)
            else estimator.named_steps["model"],
            feat_cols,
        )

        return FailureEvaluationResult(
            tag=f"{tag_prefix}-{horizon_name}-{algo_name}",
            horizon=horizon_name,
            algorithm=algo_name,
            n_train=len(y_tr),
            n_val=len(y_v),
            n_test=len(y_te),
            positive_rate_train=float(y_tr.mean()),
            positive_rate_test=float(y_te.mean()),
            pr_auc=pr_auc,
            roc_auc=roc,
            brier_score=brier,
            optimal_threshold=opt_thresh,
            precision_at_optimal=opt_m["precision"],
            recall_at_optimal=opt_m["recall"],
            f1_at_optimal=opt_m["f1"],
            metrics_at_thresholds=thresh_metrics,
            ece_before_calibration=ece_before,
            ece_after_calibration=ece_after,
            training_time_s=round(time.perf_counter() - t0, 3),
            feature_importance=fi,
        )


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _ev_to_dict(ev: FailureEvaluationResult) -> dict[str, Any]:
    from dataclasses import asdict
    return asdict(ev)
