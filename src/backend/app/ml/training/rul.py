"""
RUL (Remaining Useful Life) estimation — Phase 6.

Baselines evaluated
-------------------
1. GradientBoostingRegressor (sklearn) — strong, calibrated CI via quantile
2. XGBRegressor                        — often best on tabular
3. RandomForestRegressor               — ensemble baseline with OOB uncertainty
4. Ridge                               — linear baseline (interpretable)

Selection criterion
-------------------
Model with lowest MAE on validation set is selected and registered.
Ties broken by RMSE.

Evaluation metrics
------------------
  MAE, RMSE, R², MAPE (capped at 200%), Huber loss,
  Score function S (NASA C-MAPSS asymmetric score: sum of penalties biased
  toward late prediction, i.e. predicting OK when actually near failure).
  Prediction interval coverage (PI90: % of test points inside the 90% PI).

Uncertainty / confidence
------------------------
The selected model produces a point estimate plus a prediction interval.
For GradientBoosting: quantile regression (alpha 0.05, 0.95).
For XGB/RF: percentile of individual tree predictions.
For Ridge: residual std from training set (constant-width interval).

Safe null output
----------------
If the feature matrix for a single asset contains only NaN or has
fewer than MIN_HISTORY_ROWS rows, predict() returns a null PredictionResult
with confidence=0.0 and value=None.
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from app.ml.features.split import AssetTemporalSplitter
from app.ml.models.leakage import LeakageError, LeakageGuard
from app.ml.models.registry import ModelRegistry
from app.ml.training.utils import (
    build_X_y,
    feature_importance_dict,
    get_numeric_feature_cols,
    impute,
    leakage_pass_result,
)

# Minimum number of rows needed to trust a per-asset prediction
MIN_HISTORY_ROWS: int = 6

# RUL cap (hours) — predictions above this are clipped
RUL_CAP: float = 3000.0


# ─── Result containers ────────────────────────────────────────────────────────


@dataclass
class RULPredictionResult:
    """Single-row prediction result from RULInference."""

    component_id: str
    asset_id: str
    predicted_rul_hours: float | None      # None = insufficient data
    lower_bound: float | None              # 5th percentile
    upper_bound: float | None              # 95th percentile
    confidence: float                      # 0.0 = unreliable, 1.0 = fully confident
    feature_version: str
    model_tag: str
    predicted_at: str
    n_history_rows: int
    null_reason: str | None = None         # set when predicted_rul_hours is None


@dataclass
class RULEvaluationResult:
    """Full evaluation metrics for a trained RUL model."""

    tag: str
    algorithm: str
    n_train: int
    n_val: int
    n_test: int
    mae_val: float
    rmse_val: float
    r2_val: float
    mae_test: float
    rmse_test: float
    r2_test: float
    mape_test: float           # mean abs % error, capped at 200%
    nasa_score_test: float     # asymmetric NASA scoring function
    pi90_coverage_test: float  # 90% PI coverage on test set
    training_time_s: float
    feature_importance: dict[str, float] = field(default_factory=dict)


# ─── Baselines definition ─────────────────────────────────────────────────────

def _build_candidates(seed: int) -> dict[str, object]:
    """Return the candidate estimators for comparison."""
    return {
        "ridge": Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=1.0)),
        ]),
        "random_forest": RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=5,
            n_jobs=-1,
            random_state=seed,
            oob_score=True,
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=5,
            random_state=seed,
        ),
        "xgboost": XGBRegressor(
            n_estimators=400,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            random_state=seed,
            eval_metric="mae",
            verbosity=0,
        ),
    }


# ─── Metrics ──────────────────────────────────────────────────────────────────


def _mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0


def _mape(y_true: np.ndarray, y_pred: np.ndarray, cap: float = 2.0) -> float:
    """Mean absolute percentage error, capped at cap*100%."""
    mask = y_true >= 1.0  # avoid div-by-zero for near-zero RUL
    if mask.sum() == 0:
        return 0.0
    pct = np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])
    return float(np.mean(np.minimum(pct, cap)) * 100.0)


def _nasa_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """NASA C-MAPSS asymmetric scoring function.

    s_i = exp(-d/13) - 1  if d < 0  (early prediction — less penalty)
        = exp( d/10) - 1  if d >= 0 (late prediction — heavier penalty)
    where d = y_pred - y_true (positive = we predict MORE life remaining = optimistic).
    """
    d = y_pred - y_true
    scores = np.where(d < 0, np.exp(-d / 13.0) - 1.0, np.exp(d / 10.0) - 1.0)
    return float(np.sum(scores))


def _pi90_coverage(
    y_true: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> float:
    """Fraction of true values within [lower, upper]."""
    inside = ((y_true >= lower) & (y_true <= upper)).sum()
    return float(inside / len(y_true)) if len(y_true) > 0 else 0.0


# ─── Prediction intervals ─────────────────────────────────────────────────────


def _rf_prediction_interval(
    rf: RandomForestRegressor,
    X: np.ndarray,
    alpha_lo: float = 0.05,
    alpha_hi: float = 0.95,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-tree percentile interval for RandomForest."""
    preds = np.array([tree.predict(X) for tree in rf.estimators_])  # (n_trees, n)
    lower = np.percentile(preds, alpha_lo * 100, axis=0)
    upper = np.percentile(preds, alpha_hi * 100, axis=0)
    return lower, upper


def _xgb_prediction_interval(
    xgb: XGBRegressor,
    X: np.ndarray,
    residual_std: float,
    z: float = 1.645,
) -> tuple[np.ndarray, np.ndarray]:
    """Simple ±z·σ interval using training residual std."""
    pred = xgb.predict(X)
    return pred - z * residual_std, pred + z * residual_std


def _gb_prediction_interval(
    gb_lo: GradientBoostingRegressor,
    gb_hi: GradientBoostingRegressor,
    X: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Quantile regression interval using two separate GB models."""
    return gb_lo.predict(X), gb_hi.predict(X)


# ─── Main trainer ─────────────────────────────────────────────────────────────


class RULTrainer:
    """Train and compare baseline RUL models.

    Parameters
    ----------
    seed:
        Global random seed. Fixed for reproducibility.
    registry:
        ModelRegistry instance for persisting artifacts.
    rul_cap:
        Clip predictions above this value (hours).
    """

    def __init__(
        self,
        seed: int = 42,
        registry: ModelRegistry | None = None,
        rul_cap: float = RUL_CAP,
    ) -> None:
        self.seed = seed
        self.registry = registry or ModelRegistry()
        self.rul_cap = rul_cap

    def train(
        self,
        features_df: pd.DataFrame,
        labels_df: pd.DataFrame,
        failure_events_df: pd.DataFrame | None = None,
        tag_prefix: str = "rul",
    ) -> tuple[str, dict[str, RULEvaluationResult]]:
        """Train all candidates, evaluate, register the best.

        Returns
        -------
        (selected_tag, evaluation_results_by_algo)
        """
        # Asset-level split
        splitter = AssetTemporalSplitter(seed=self.seed)
        split = splitter.split(features_df, failure_events_df)
        train_f, val_f, test_f = split.apply(features_df)

        # Build X, y for each split
        X_train, y_train, feat_cols = build_X_y(
            train_f, labels_df, "rul_cycles", "rul"
        )
        X_val, y_val, _ = build_X_y(val_f, labels_df, "rul_cycles", "rul",
                                      feature_cols=feat_cols)
        X_test, y_test, _ = build_X_y(test_f, labels_df, "rul_cycles", "rul",
                                        feature_cols=feat_cols)

        if len(X_train) < 50:
            raise ValueError(
                f"Training set too small ({len(X_train)} rows) for RUL training. "
                "Run a larger simulation profile (e.g. validation.yaml)."
            )

        # Impute (fit on train only)
        X_tr, X_v, X_te, imputer = impute(X_train, X_val, X_test)

        y_tr = y_train.values.astype(float)
        y_v = y_val.values.astype(float)
        y_te = y_test.values.astype(float)

        candidates = _build_candidates(self.seed)
        results: dict[str, RULEvaluationResult] = {}

        for algo_name, estimator in candidates.items():
            t0 = time.perf_counter()

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                estimator.fit(X_tr.values, y_tr)

            train_time = time.perf_counter() - t0

            pv = np.clip(estimator.predict(X_v.values), 0.0, self.rul_cap)
            pt = np.clip(estimator.predict(X_te.values), 0.0, self.rul_cap)

            # Prediction interval on test set
            lower_te, upper_te = self._prediction_interval(
                algo_name, estimator, X_tr.values, y_tr, X_te.values
            )
            lower_te = np.clip(lower_te, 0.0, self.rul_cap)
            upper_te = np.clip(upper_te, 0.0, self.rul_cap)

            fi = feature_importance_dict(
                estimator if not isinstance(estimator, Pipeline)
                else estimator.named_steps["model"],
                feat_cols,
            )

            ev = RULEvaluationResult(
                tag=f"{tag_prefix}-{algo_name}",
                algorithm=algo_name,
                n_train=len(y_tr),
                n_val=len(y_v),
                n_test=len(y_te),
                mae_val=_mae(y_v, pv),
                rmse_val=_rmse(y_v, pv),
                r2_val=_r2(y_v, pv),
                mae_test=_mae(y_te, pt),
                rmse_test=_rmse(y_te, pt),
                r2_test=_r2(y_te, pt),
                mape_test=_mape(y_te, pt),
                nasa_score_test=_nasa_score(y_te, pt),
                pi90_coverage_test=_pi90_coverage(y_te, lower_te, upper_te),
                training_time_s=round(train_time, 3),
                feature_importance=fi,
            )
            results[algo_name] = ev

        # Select by lowest val MAE; break ties with RMSE
        best_algo = min(
            results,
            key=lambda a: (results[a].mae_val, results[a].rmse_val),
        )
        best_result = results[best_algo]
        best_estimator = candidates[best_algo]

        # Re-fit best on train+val combined for deployment
        X_trainval = np.vstack([X_tr.values, X_v.values])
        y_trainval = np.concatenate([y_tr, y_v])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            best_estimator.fit(X_trainval, y_trainval)

        # Build quantile models for PI (GB only — for others use residual std)
        pi_lo, pi_hi = self._fit_pi_models(
            best_algo, best_estimator, X_trainval, y_trainval,
            X_te.values, y_te
        )

        # Leakage check result
        leakage_result = leakage_pass_result(feat_cols)

        selected_tag = f"{tag_prefix}-{best_algo}-v1"

        training_metadata = {
            "seed": self.seed,
            "algorithm": best_algo,
            "split_metadata": split.split_metadata,
            "feature_cols": feat_cols,
            "imputer_strategy": "median",
            "rul_cap": self.rul_cap,
            "n_candidates_compared": len(candidates),
            "candidate_algos": list(candidates.keys()),
            "selection_criterion": "lowest_val_mae",
        }

        self.registry.register(
            task="rul",
            tag=selected_tag,
            estimator={"model": best_estimator, "imputer": imputer,
                        "pi_lo": pi_lo, "pi_hi": pi_hi},
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

    # ─── PI helpers ───────────────────────────────────────────────────────────

    def _prediction_interval(
        self,
        algo_name: str,
        estimator: object,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute 90% prediction interval for test set."""
        if algo_name == "random_forest":
            return _rf_prediction_interval(estimator, X_test)
        # For all others: residual std from training set predictions
        y_pred_train = np.clip(estimator.predict(X_train), 0.0, self.rul_cap)
        residual_std = float(np.std(y_train - y_pred_train))
        z = 1.645
        y_pred_test = np.clip(estimator.predict(X_test), 0.0, self.rul_cap)
        return y_pred_test - z * residual_std, y_pred_test + z * residual_std

    def _fit_pi_models(
        self,
        algo_name: str,
        estimator: object,
        X_trainval: np.ndarray,
        y_trainval: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
    ) -> tuple[object | None, object | None]:
        """Fit quantile regression lower/upper models for deployment PI."""
        if algo_name != "gradient_boosting":
            return None, None
        gb_lo = GradientBoostingRegressor(
            loss="quantile", alpha=0.05,
            n_estimators=200, max_depth=4, learning_rate=0.05,
            random_state=self.seed,
        )
        gb_hi = GradientBoostingRegressor(
            loss="quantile", alpha=0.95,
            n_estimators=200, max_depth=4, learning_rate=0.05,
            random_state=self.seed,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gb_lo.fit(X_trainval, y_trainval)
            gb_hi.fit(X_trainval, y_trainval)
        return gb_lo, gb_hi


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _ev_to_dict(ev: RULEvaluationResult) -> dict[str, Any]:
    from dataclasses import asdict
    return asdict(ev)
