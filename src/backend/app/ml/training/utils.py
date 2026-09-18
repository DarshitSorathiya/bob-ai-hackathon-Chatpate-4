"""
Shared training utilities for Phase 6 ML models.

Responsibilities
----------------
- build_X_y(): join features + labels, select feature columns, run leakage check
- get_numeric_feature_cols(): return ML-usable numeric feature columns from a features_df
- impute_and_scale(): median imputation + optional scaling for tree models
- feature_importance_dict(): extract importance from sklearn/XGB/LGB estimators
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer

from app.ml.models.leakage import LeakageGuard

# Columns that are join keys or metadata — never ML features
_NON_FEATURE_COLS: frozenset[str] = frozenset({
    "asset_id",
    "sensor_id",
    "component_id",
    "recorded_at",
    "timestamp",
    "operating_condition",
    "source",
    "is_clean",
    "quality_flag",
    "quality_reason",
    "operating_hours",   # raw cumulative — can be context feature via context pipeline
    # truth/label columns (belt-and-suspenders)
    "true_health", "true_rul", "latent_health", "degradation_multiplier",
    "archetype", "failure_label", "failure_event", "failure_timestamp",
    "rul_cycles", "failure_within_24h", "failure_within_72h",
    "failure_within_window", "health_class",
})


def get_numeric_feature_cols(features_df: pd.DataFrame) -> list[str]:
    """Return sorted list of numeric columns safe to use as ML features."""
    numeric_cols = features_df.select_dtypes(include=[np.number]).columns.tolist()
    return sorted(c for c in numeric_cols if c not in _NON_FEATURE_COLS)


def build_X_y(
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    label_col: str,
    task: str,
    join_keys: tuple[str, str] = ("component_id", "timestamp"),
    feature_cols: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Join features with labels and return (X, y, feature_col_list).

    The join is LEFT features → labels so every feature row gets its label.
    Rows where the label is NaN after the join are dropped.

    Parameters
    ----------
    features_df:
        Feature DataFrame (no truth columns).
    labels_df:
        Labels DataFrame from LabelGenerator.generate().
    label_col:
        Name of the label column in labels_df (e.g. "rul_cycles").
    task:
        One of 'rul', 'failure', 'anomaly' — passed to LeakageGuard.
    join_keys:
        (feature_key, label_key) column names to join on.
        Default: ("component_id", "timestamp") — features use "recorded_at"
        while labels use "timestamp"; caller may override.
    feature_cols:
        Explicit list of feature columns. If None, inferred via
        get_numeric_feature_cols().

    Returns
    -------
    X, y, feature_cols
    """
    feat_key, label_key = join_keys

    # Normalise timestamp keys so the join works
    feats = features_df.copy()
    labs = labels_df.copy()

    # Align timestamp column name for the join
    if feat_key == "recorded_at" or feat_key not in feats.columns:
        feat_key = "recorded_at"
    if label_key == "timestamp" or label_key not in labs.columns:
        label_key = "timestamp"

    # Normalize timestamp representations before joining. Parquet-backed
    # features may use a datetime with a space separator, while labels are
    # emitted as ISO strings with a ``T`` separator.
    feats["_join_ts"] = pd.to_datetime(feats["recorded_at"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%S")
    labs["_join_ts"] = pd.to_datetime(labs["timestamp"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%S")

    merged = feats.merge(
        labs[["component_id", "_join_ts", label_col]],
        on=["component_id", "_join_ts"],
        how="left",
    ).drop(columns=["_join_ts"])

    # Drop rows with missing label
    merged = merged.dropna(subset=[label_col]).copy()

    if feature_cols is None:
        feature_cols = get_numeric_feature_cols(merged)

    # Drop the label col from feature_cols if somehow present
    feature_cols = [c for c in feature_cols if c != label_col]

    X = merged[feature_cols].copy()
    y = merged[label_col].copy()

    # Run leakage check — raises LeakageError if any violation found
    LeakageGuard.check(X, y_col=label_col, task=task)

    return X, y, feature_cols


def impute(
    X_train: pd.DataFrame,
    X_val: pd.DataFrame | None = None,
    X_test: pd.DataFrame | None = None,
    strategy: str = "median",
) -> tuple:
    """Fit imputer on train, apply to val/test. Returns imputed copies.

    Returns (X_train_imp, X_val_imp, X_test_imp, imputer).
    Val and test are None if not provided.
    """
    # Keep columns that are empty in one asset split. Sensor-specific feature
    # columns are legitimately absent for other asset types; dropping them
    # here changes the registered feature schema and breaks inference.
    try:
        imp = SimpleImputer(strategy=strategy, keep_empty_features=True)
    except TypeError:  # compatibility with older scikit-learn releases
        imp = SimpleImputer(strategy=strategy)
    X_tr = pd.DataFrame(
        imp.fit_transform(X_train),
        columns=X_train.columns,
        index=X_train.index,
    )
    X_v = (
        pd.DataFrame(imp.transform(X_val), columns=X_val.columns, index=X_val.index)
        if X_val is not None else None
    )
    X_te = (
        pd.DataFrame(imp.transform(X_test), columns=X_test.columns, index=X_test.index)
        if X_test is not None else None
    )
    return X_tr, X_v, X_te, imp


def feature_importance_dict(
    estimator: object,
    feature_names: list[str],
) -> dict[str, float]:
    """Extract feature importance from sklearn/XGB/LGB estimators.

    Returns a dict {feature_name: importance} sorted by descending importance.
    Returns empty dict if the estimator has no feature_importances_ attribute.
    """
    importances: np.ndarray | None = None

    if hasattr(estimator, "feature_importances_"):
        importances = np.array(estimator.feature_importances_)
    elif hasattr(estimator, "coef_"):
        importances = np.abs(np.array(estimator.coef_).ravel())

    if importances is None or len(importances) != len(feature_names):
        return {}

    total = importances.sum()
    if total > 0:
        importances = importances / total

    paired = sorted(
        zip(feature_names, importances.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )
    return dict(paired)


def leakage_pass_result(feature_names: list[str]) -> dict[str, Any]:
    """Return a leakage_result dict with status=PASS."""
    from app.ml.models.leakage import LeakageGuard
    dummy = pd.DataFrame(columns=feature_names)
    violations = LeakageGuard.report(dummy)
    return {
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "n_features_checked": len(feature_names),
        "feature_hash": hashlib.sha256(",".join(sorted(feature_names)).encode()).hexdigest()[:12],
    }
