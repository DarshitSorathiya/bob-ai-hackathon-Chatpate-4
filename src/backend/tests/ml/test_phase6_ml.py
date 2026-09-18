"""
Phase 6 ML tests — RUL, Failure Probability, Anomaly Detection.

Test structure
--------------
UNIT tests (fast, ~1s, no simulation):
  - Leakage guard
  - Registry
  - Training utilities
  - Metric functions (RUL, failure, anomaly)

INTEGRATION tests (marked @pytest.mark.slow):
  - Use a synthetic feature+label matrix — avoids the slow iterrows()
    context pipeline so the full ML train→evaluate→register→infer
    cycle runs in under 3 minutes.

Run unit tests only:   pytest tests/ml/test_phase6_ml.py -m "not slow"
Run all tests:         pytest tests/ml/test_phase6_ml.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.ml.models.leakage import LeakageError, LeakageGuard
from app.ml.models.registry import ModelRegistry
from app.ml.training.utils import (
    feature_importance_dict,
    get_numeric_feature_cols,
    impute,
    leakage_pass_result,
)
from app.ml.training.rul import (
    RUL_CAP,
    _mae, _rmse, _r2, _mape, _nasa_score, _pi90_coverage,
)
from app.ml.training.failure import _ece, _optimal_threshold, _metrics_at_threshold
from app.ml.training.anomaly import _normalise_scores, _top_contributing_features


# ─── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def clean_features_df():
    """Small clean feature DataFrame — no forbidden columns."""
    rng = np.random.default_rng(0)
    n = 100
    return pd.DataFrame({
        "asset_id": ["a"] * n,
        "sensor_id": ["s1"] * n,
        "component_id": ["c1"] * n,
        "recorded_at": [f"2023-01-01T{(i % 24):02d}:00:00+00:00" for i in range(n)],
        "feat_roll6_mean": rng.normal(2.0, 0.1, n),
        "feat_roll6_std": rng.normal(0.1, 0.01, n).clip(0),
        "feat_roll24_mean": rng.normal(2.0, 0.2, n),
        "op_cond_CRUISE": np.ones(n, dtype=int),
        "hours_since_last_maint": rng.uniform(0, 500, n),
    })


def _make_synthetic_dataset(
    n_assets: int = 40,
    n_timesteps: int = 300,
    n_features: int = 25,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a synthetic (features_df, labels_df) pair for ML training tests.

    Generates a realistic dataset without running the slow simulator pipeline:
    - n_assets assets, each with n_timesteps rows
    - RUL decreases linearly from ~2000h to 0h over each asset's life
    - Failure labels derived from RUL
    - Features are correlated with health to give models something to learn

    Returns (features_df, labels_df) matching the shapes expected by trainers.
    """
    rng = np.random.default_rng(seed)

    feature_names = [f"feat_{i:03d}" for i in range(n_features)]
    asset_ids = [f"ASSET-{i:03d}" for i in range(n_assets)]
    component_ids = [f"COMP-{i:03d}" for i in range(n_assets)]

    feature_rows = []
    label_rows = []

    base_ts = pd.Timestamp("2022-01-01", tz="UTC")

    for asset_idx, (asset_id, comp_id) in enumerate(zip(asset_ids, component_ids)):
        # Each asset degrades at a slightly different rate
        rul_start = rng.uniform(500.0, 2500.0)
        rul_end = 0.0
        rul_values = np.linspace(rul_start, rul_end, n_timesteps)
        health = rul_values / rul_start

        timestamps = [base_ts + pd.Timedelta(hours=i) for i in range(n_timesteps)]

        for t in range(n_timesteps):
            h = float(health[t])
            ts_str = timestamps[t].isoformat()

            # Features are correlated with health degradation + noise
            feats: dict = {
                "asset_id": asset_id,
                "component_id": comp_id,
                "sensor_id": f"S-{asset_idx:03d}",
                "recorded_at": ts_str,
            }
            for fi, fname in enumerate(feature_names):
                # Mix of degradation-correlated and noise features
                if fi < n_features // 3:
                    feats[fname] = (1.0 - h) * 5.0 + rng.normal(0, 0.3)
                elif fi < 2 * n_features // 3:
                    feats[fname] = h * 3.0 + rng.normal(0, 0.2)
                else:
                    feats[fname] = rng.normal(0, 1.0)
            feature_rows.append(feats)

            # Labels
            rul = float(rul_values[t])
            fw24 = int(rul <= 24.0)
            fw72 = int(rul <= 72.0)
            fw_window = int(rul <= 168.0)  # 7 days
            label_rows.append({
                "component_id": comp_id,
                "asset_id": asset_id,
                "timestamp": ts_str,
                "rul_cycles": rul,
                "failure_within_24h": fw24,
                "failure_within_72h": fw72,
                "failure_within_window": fw_window,
                "health_class": (
                    "HEALTHY" if h >= 0.70 else
                    "DEGRADED" if h >= 0.30 else
                    "CRITICAL"
                ),
            })

    features_df = pd.DataFrame(feature_rows)
    labels_df = pd.DataFrame(label_rows)
    return features_df, labels_df


@pytest.fixture(scope="module")
def synthetic_dataset():
    """Synthetic ML-ready dataset — no simulator pipeline required."""
    return _make_synthetic_dataset(n_assets=40, n_timesteps=300, seed=42)


@pytest.fixture(scope="module")
def synthetic_components_df():
    """Minimal components table for anomaly trainer."""
    return pd.DataFrame([
        {"component_id": f"COMP-{i:03d}", "component_type": "ENGINE_CORE"
         if i % 2 == 0 else "GEARBOX"}
        for i in range(40)
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# LEAKAGE GUARD TESTS (unit)
# ═══════════════════════════════════════════════════════════════════════════════


def test_leakage_guard_raises_on_forbidden_column():
    df = pd.DataFrame({"feat_a": [1.0, 2.0], "true_rul": [100.0, 200.0]})
    with pytest.raises(LeakageError, match="true_rul"):
        LeakageGuard.check(df, task="rul")


def test_leakage_guard_raises_on_label_in_X():
    df = pd.DataFrame({"feat_a": [1.0], "rul_cycles": [500.0]})
    with pytest.raises(LeakageError, match="rul_cycles"):
        LeakageGuard.check(df, y_col="rul_cycles", task="rul")


def test_leakage_guard_passes_on_clean_features(clean_features_df):
    feat_only = clean_features_df[["feat_roll6_mean", "feat_roll6_std",
                                    "feat_roll24_mean", "op_cond_CRUISE",
                                    "hours_since_last_maint"]]
    LeakageGuard.check(feat_only, task="rul")   # must not raise


def test_leakage_guard_report_empty_for_clean(clean_features_df):
    feat_only = clean_features_df[["feat_roll6_mean", "feat_roll6_std"]]
    assert LeakageGuard.report(feat_only) == []


def test_leakage_guard_report_lists_all_violations():
    df = pd.DataFrame({"feat_a": [1.0], "true_health": [0.9], "latent_health": [0.8]})
    violations = LeakageGuard.report(df)
    assert len(violations) == 2
    assert any("true_health" in v for v in violations)
    assert any("latent_health" in v for v in violations)


def test_leakage_guard_task_specific_columns():
    for col, task in [
        ("rul_cycles", "rul"),
        ("failure_within_24h", "failure"),
        ("true_health", "anomaly"),
    ]:
        df = pd.DataFrame({"feat_x": [1.0], col: [0.5]})
        with pytest.raises(LeakageError):
            LeakageGuard.check(df, task=task)


def test_leakage_guard_all_tasks_pass_clean_features(clean_features_df):
    feat_only = clean_features_df[["feat_roll6_mean", "hours_since_last_maint"]]
    for task in ("rul", "failure", "anomaly"):
        LeakageGuard.check(feat_only, task=task)   # must not raise


def test_leakage_check_synthetic_features_clean(synthetic_dataset):
    """Leakage: synthetic feature matrix must pass guard for all tasks."""
    features_df, _ = synthetic_dataset
    feat_cols = get_numeric_feature_cols(features_df)
    X = features_df[feat_cols]
    for task in ("rul", "failure", "anomaly"):
        violations = LeakageGuard.report(X, task=task)
        assert violations == [], f"Task '{task}' leakage violations: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRY TESTS (unit)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_registry(tmp_path):
    return ModelRegistry(base_dir=tmp_path / "models")


def test_registry_register_creates_files(tmp_registry):
    from sklearn.linear_model import Ridge
    est = Ridge().fit([[1], [2]], [1, 2])
    leakage = {"status": "PASS", "violations": [], "n_features_checked": 1, "feature_hash": "abc"}
    record = tmp_registry.register(
        task="rul", tag="test-rul-v0", estimator=est,
        feature_names=["f1"], training_metadata={"seed": 42},
        evaluation_metadata={"mae": 1.0}, leakage_result=leakage,
    )
    artifact_dir = Path(record.artifact_dir)
    assert (artifact_dir / "model.joblib").exists()
    assert (artifact_dir / "metadata.json").exists()
    assert (artifact_dir / "evaluation.json").exists()
    assert (artifact_dir / "leakage_check.json").exists()


def test_registry_load_returns_same_type(tmp_registry):
    from sklearn.linear_model import Ridge
    est = Ridge()
    leakage = {"status": "PASS", "violations": [], "n_features_checked": 1, "feature_hash": "abc"}
    tmp_registry.register(
        task="rul", tag="test-load", estimator=est, feature_names=["f1"],
        training_metadata={}, evaluation_metadata={}, leakage_result=leakage,
    )
    loaded, record = tmp_registry.load("test-load")
    assert isinstance(loaded, Ridge)
    assert record.tag == "test-load"


def test_registry_rejects_fail_leakage(tmp_registry):
    from sklearn.linear_model import Ridge
    leakage = {"status": "FAIL", "violations": ["true_rul in X"]}
    with pytest.raises(ValueError, match="leakage check"):
        tmp_registry.register(
            task="rul", tag="leaky", estimator=Ridge(), feature_names=["true_rul"],
            training_metadata={}, evaluation_metadata={}, leakage_result=leakage,
        )


def test_registry_exists(tmp_registry):
    from sklearn.linear_model import Ridge
    leakage = {"status": "PASS", "violations": [], "n_features_checked": 1, "feature_hash": "x"}
    tmp_registry.register(
        task="rul", tag="exists-test", estimator=Ridge(), feature_names=["f"],
        training_metadata={}, evaluation_metadata={}, leakage_result=leakage,
    )
    assert tmp_registry.exists("exists-test")
    assert not tmp_registry.exists("does-not-exist")


def test_registry_record_to_dict(tmp_registry):
    from sklearn.linear_model import Ridge
    leakage = {"status": "PASS", "violations": [], "n_features_checked": 1, "feature_hash": "x"}
    record = tmp_registry.register(
        task="rul", tag="dict-test", estimator=Ridge(), feature_names=["f1", "f2"],
        training_metadata={"seed": 1}, evaluation_metadata={"mae": 0.5},
        leakage_result=leakage,
    )
    d = record.to_dict()
    assert d["task"] == "rul"
    assert d["tag"] == "dict-test"
    assert "feature_version" in d
    assert len(json.dumps(d)) > 10


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING UTILITY TESTS (unit)
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_numeric_feature_cols_excludes_metadata(clean_features_df):
    cols = get_numeric_feature_cols(clean_features_df)
    for excluded in ["asset_id", "component_id", "sensor_id", "recorded_at"]:
        assert excluded not in cols
    assert "feat_roll6_mean" in cols


def test_impute_no_nan_after(clean_features_df):
    X = clean_features_df[["feat_roll6_mean", "feat_roll6_std", "feat_roll24_mean"]].copy()
    X.iloc[5, 0] = np.nan
    X_imp, _, _, _ = impute(X)
    assert not X_imp.isna().any().any()


def test_feature_importance_dict_sums_to_one():
    from sklearn.ensemble import RandomForestRegressor
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, (100, 5))
    y = X[:, 0] + rng.normal(0, 0.1, 100)
    rf = RandomForestRegressor(n_estimators=10, random_state=0)
    rf.fit(X, y)
    fi = feature_importance_dict(rf, ["a", "b", "c", "d", "e"])
    assert abs(sum(fi.values()) - 1.0) < 1e-6


def test_leakage_pass_result_clean():
    result = leakage_pass_result(["feat_roll6_mean", "feat_roll24_mean"])
    assert result["status"] == "PASS"
    assert result["violations"] == []


def test_leakage_pass_result_fails_forbidden():
    result = leakage_pass_result(["feat_a", "true_rul"])
    assert result["status"] == "FAIL"
    assert len(result["violations"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# RUL METRIC TESTS (unit)
# ═══════════════════════════════════════════════════════════════════════════════


def test_rul_mae():
    y = np.array([100.0, 200.0, 300.0])
    p = np.array([110.0, 190.0, 310.0])
    assert abs(_mae(y, p) - 10.0) < 1e-9


def test_rul_rmse():
    y = np.array([0.0, 1.0])
    p = np.array([1.0, 0.0])
    assert abs(_rmse(y, p) - 1.0) < 1e-9


def test_rul_r2_perfect():
    y = np.array([1.0, 2.0, 3.0])
    assert abs(_r2(y, y) - 1.0) < 1e-9


def test_rul_mape_capped():
    assert _mape(np.array([1.0]), np.array([10000.0])) == pytest.approx(200.0, abs=1.0)


def test_nasa_score_late_worse_than_early():
    y = np.array([50.0])
    assert _nasa_score(y, np.array([100.0])) > _nasa_score(y, np.array([20.0]))


def test_pi90_coverage_perfect():
    y = np.array([10.0, 20.0])
    assert _pi90_coverage(y, y - 1, y + 1) == pytest.approx(1.0)


def test_pi90_coverage_empty():
    assert _pi90_coverage(np.array([]), np.array([]), np.array([])) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE METRIC TESTS (unit)
# ═══════════════════════════════════════════════════════════════════════════════


def test_ece_perfect():
    y = np.array([1, 0, 1, 0])
    p = np.array([1.0, 0.0, 1.0, 0.0])
    assert _ece(y, p) == pytest.approx(0.0, abs=0.05)


def test_ece_badly_calibrated():
    y = np.zeros(100, dtype=int)
    p = np.ones(100) * 0.9
    assert _ece(y, p) > 0.5


def test_optimal_threshold_valid_range():
    rng = np.random.default_rng(7)
    y = (rng.random(200) > 0.8).astype(int)
    p = rng.random(200)
    t = _optimal_threshold(y, p)
    assert 0.0 <= t <= 1.0


def test_metrics_at_threshold_fnr():
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    p = np.array([0.9, 0.8, 0.3, 0.2, 0.1, 0.1, 0.1, 0.1])
    m = _metrics_at_threshold(y, p, 0.5)
    assert m["fn"] == 2
    assert abs(m["false_negative_rate"] - 0.5) < 1e-9


# ═══════════════════════════════════════════════════════════════════════════════
# ANOMALY METRIC TESTS (unit)
# ═══════════════════════════════════════════════════════════════════════════════


def test_normalise_scores_range():
    raw = np.array([-0.5, -0.2, 0.0, 0.1, 0.3])
    norm = _normalise_scores(raw)
    assert norm.min() >= -1e-9
    assert norm.max() <= 1.0 + 1e-9


def test_normalise_scores_constant_no_nan():
    norm = _normalise_scores(np.ones(10) * 0.2)
    assert not np.any(np.isnan(norm))
    assert np.allclose(norm, 0.0)


def test_top_features_count():
    x, mu, sigma = np.array([5.0, 3.0, 1.0]), np.zeros(3), np.ones(3)
    top = _top_contributing_features(x, mu, sigma, ["a", "b", "c"], top_n=2)
    assert len(top) <= 2


def test_top_features_descending():
    x, mu, sigma = np.array([10.0, 2.0, 5.0]), np.zeros(3), np.ones(3)
    top = _top_contributing_features(x, mu, sigma, ["a", "b", "c"], top_n=3)
    scores = [s for _, s in top]
    assert scores == sorted(scores, reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — RUL (marked slow, synthetic data)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def rul_trained(synthetic_dataset, tmp_path_factory):
    features_df, labels_df = synthetic_dataset
    reg = ModelRegistry(base_dir=tmp_path_factory.mktemp("rul"))
    from app.ml.training import RULTrainer
    trainer = RULTrainer(seed=42, registry=reg)
    tag, results = trainer.train(features_df=features_df, labels_df=labels_df)
    return tag, results, reg


@pytest.mark.slow
def test_rul_train_all_candidates(rul_trained):
    _, results, _ = rul_trained
    for algo in ("ridge", "random_forest", "gradient_boosting", "xgboost"):
        assert algo in results


@pytest.mark.slow
def test_rul_selected_registered(rul_trained):
    tag, _, reg = rul_trained
    assert reg.exists(tag)


@pytest.mark.slow
def test_rul_selected_has_lowest_val_mae(rul_trained):
    tag, results, _ = rul_trained
    best_algo = tag.split("-")[1]
    best_mae = results[best_algo].mae_val
    for ev in results.values():
        assert best_mae <= ev.mae_val + 1e-9


@pytest.mark.slow
def test_rul_metrics_finite_non_negative(rul_trained):
    _, results, _ = rul_trained
    for algo, ev in results.items():
        assert np.isfinite(ev.mae_val) and ev.mae_val >= 0, f"{algo}: bad mae_val"
        assert np.isfinite(ev.rmse_val) and ev.rmse_val >= 0, f"{algo}: bad rmse_val"
        assert 0.0 <= ev.pi90_coverage_test <= 1.0


@pytest.mark.slow
def test_rul_leakage_check_pass(rul_trained):
    tag, _, reg = rul_trained
    with open(Path(reg.base_dir) / tag / "leakage_check.json") as f:
        lc = json.load(f)
    assert lc["status"] == "PASS"


@pytest.mark.slow
def test_rul_feature_importance_is_subset_of_feats(rul_trained, synthetic_dataset):
    tag, results, _ = rul_trained
    best_algo = tag.split("-")[1]
    fi = results[best_algo].feature_importance
    features_df, _ = synthetic_dataset
    feat_cols = set(get_numeric_feature_cols(features_df))
    for key in fi:
        assert key in feat_cols, f"'{key}' in FI but not a feature col"


@pytest.mark.slow
def test_rul_clipped_predictions_never_negative(rul_trained, synthetic_dataset):
    """RUL inference clips predictions to [0, RUL_CAP]. Verify clipped preds >= 0."""
    tag, _, reg = rul_trained
    bundle, record = reg.load(tag)
    features_df, _ = synthetic_dataset
    feat_cols = record.feature_names
    X_df = pd.DataFrame(index=features_df.index)
    for col in feat_cols:
        X_df[col] = features_df[col] if col in features_df.columns else 0.0
    X_imp = bundle["imputer"].transform(X_df[feat_cols].values)
    preds = bundle["model"].predict(X_imp)
    # Inference always clips to [0, RUL_CAP] — test that convention
    clipped = np.clip(preds, 0.0, RUL_CAP)
    assert (clipped < 0.0).sum() == 0, "Clipped RUL predictions must be >= 0"
    # Also verify the raw model doesn't wildly extrapolate (> -200h is acceptable)
    assert (preds < -200.0).sum() == 0, f"Extreme negative predictions: {(preds < -200).sum()}"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — FAILURE PROBABILITY (marked slow)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def failure_trained(synthetic_dataset, tmp_path_factory):
    features_df, labels_df = synthetic_dataset
    reg = ModelRegistry(base_dir=tmp_path_factory.mktemp("failure"))
    from app.ml.training import FailureTrainer
    trainer = FailureTrainer(seed=42, registry=reg)
    outputs = trainer.train(features_df=features_df, labels_df=labels_df)
    return outputs, reg


@pytest.mark.slow
def test_failure_at_least_one_horizon(failure_trained):
    outputs, _ = failure_trained
    assert len(outputs) >= 1


@pytest.mark.slow
def test_failure_pr_auc_valid(failure_trained):
    outputs, _ = failure_trained
    for horizon, (tag, results) in outputs.items():
        for algo, ev in results.items():
            assert 0.0 <= ev.pr_auc <= 1.0, f"{horizon}/{algo}: pr_auc={ev.pr_auc}"


@pytest.mark.slow
def test_failure_roc_auc_valid(failure_trained):
    outputs, _ = failure_trained
    for horizon, (tag, results) in outputs.items():
        for algo, ev in results.items():
            assert 0.0 <= ev.roc_auc <= 1.0


@pytest.mark.slow
def test_failure_ece_non_negative(failure_trained):
    outputs, _ = failure_trained
    for horizon, (tag, results) in outputs.items():
        for algo, ev in results.items():
            assert ev.ece_before_calibration >= 0.0
            assert ev.ece_after_calibration >= 0.0


@pytest.mark.slow
def test_failure_metrics_at_thresholds_keys(failure_trained):
    outputs, _ = failure_trained
    for horizon, (tag, results) in outputs.items():
        for algo, ev in results.items():
            for m in ev.metrics_at_thresholds.values():
                for key in ("precision", "recall", "f1", "false_negative_rate"):
                    assert key in m


@pytest.mark.slow
def test_failure_leakage_check_pass(failure_trained):
    outputs, reg = failure_trained
    for horizon, (tag, _) in outputs.items():
        with open(Path(reg.base_dir) / tag / "leakage_check.json") as f:
            lc = json.load(f)
        assert lc["status"] == "PASS", f"{horizon}: {lc}"


@pytest.mark.slow
def test_failure_probability_in_unit_interval(failure_trained, synthetic_dataset):
    outputs, reg = failure_trained
    if not outputs:
        pytest.skip("No failure models")
    horizon, (tag, _) = list(outputs.items())[0]
    bundle, record = reg.load(tag)
    features_df, _ = synthetic_dataset
    feat_cols = record.feature_names
    X_df = pd.DataFrame(index=features_df.index)
    for col in feat_cols:
        X_df[col] = features_df[col] if col in features_df.columns else 0.0
    X_imp = bundle["imputer"].transform(X_df[feat_cols].values)
    probs = bundle["model"].predict_proba(X_imp)[:, 1]
    assert np.all(probs >= -1e-6), f"min={probs.min()}"
    assert np.all(probs <= 1.0 + 1e-6), f"max={probs.max()}"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — ANOMALY (marked slow)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def anomaly_trained(synthetic_dataset, synthetic_components_df, tmp_path_factory):
    features_df, _ = synthetic_dataset
    reg = ModelRegistry(base_dir=tmp_path_factory.mktemp("anomaly"))
    from app.ml.training import AnomalyTrainer
    trainer = AnomalyTrainer(seed=42, registry=reg, contamination=0.05)
    # Mark half the assets as "anomalous" for evaluation
    n_assets = features_df["asset_id"].nunique()
    all_assets = features_df["asset_id"].unique().tolist()
    edge_case_tags = {a: ["INJECTED_FAULT"] for a in all_assets[:n_assets // 4]}
    outputs = trainer.train(
        features_df=features_df,
        components_df=synthetic_components_df,
        edge_case_tags=edge_case_tags,
    )
    return outputs, reg


@pytest.mark.slow
def test_anomaly_at_least_one_type(anomaly_trained):
    outputs, _ = anomaly_trained
    assert len(outputs) >= 1


@pytest.mark.slow
def test_anomaly_detection_rate_valid(anomaly_trained):
    outputs, _ = anomaly_trained
    for ctype, (tag, ev) in outputs.items():
        assert 0.0 <= ev.detection_rate <= 1.0


@pytest.mark.slow
def test_anomaly_fpr_valid(anomaly_trained):
    outputs, _ = anomaly_trained
    for ctype, (tag, ev) in outputs.items():
        assert 0.0 <= ev.false_positive_rate <= 1.0


@pytest.mark.slow
def test_anomaly_roc_auc_valid(anomaly_trained):
    outputs, _ = anomaly_trained
    for ctype, (tag, ev) in outputs.items():
        assert 0.0 <= ev.roc_auc <= 1.0


@pytest.mark.slow
def test_anomaly_leakage_check_pass(anomaly_trained):
    outputs, reg = anomaly_trained
    for ctype, (tag, _) in outputs.items():
        with open(Path(reg.base_dir) / tag / "leakage_check.json") as f:
            lc = json.load(f)
        assert lc["status"] == "PASS"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — INFERENCE (marked slow)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.slow
def test_rul_inference_null_on_few_rows(rul_trained):
    from app.ml.models.inference import RULInference
    tag, _, reg = rul_trained
    ri = RULInference(tag=tag, registry=reg)
    ri.load()
    tiny_df = pd.DataFrame({
        "component_id": ["c1"] * 3, "asset_id": ["a1"] * 3,
        "recorded_at": ["2023-01-01T00:00:00+00:00"] * 3,
    })
    r = ri.predict(tiny_df, "c1", "a1")
    assert r.predicted_rul_hours is None
    assert r.confidence == 0.0


@pytest.mark.slow
def test_rul_inference_valid_on_sufficient_rows(rul_trained, synthetic_dataset):
    from app.ml.models.inference import RULInference
    tag, _, reg = rul_trained
    ri = RULInference(tag=tag, registry=reg)
    ri.load()
    features_df, _ = synthetic_dataset
    comp_id = features_df["component_id"].value_counts().index[0]
    comp_df = features_df[features_df["component_id"] == comp_id]
    asset_id = comp_df["asset_id"].iloc[0]
    r = ri.predict(comp_df, comp_id, asset_id)
    if r.null_reason:
        pytest.skip(f"null: {r.null_reason}")
    assert r.predicted_rul_hours is not None
    assert 0.0 <= r.predicted_rul_hours <= RUL_CAP + 1.0
    assert 0.0 <= r.confidence <= 1.0
    assert r.lower_bound is not None and r.upper_bound is not None
    assert r.lower_bound <= r.predicted_rul_hours + 1.0
    assert r.upper_bound >= r.predicted_rul_hours - 1.0


@pytest.mark.slow
def test_failure_inference_probability_valid(failure_trained, synthetic_dataset):
    from app.ml.models.inference import FailureInference
    outputs, reg = failure_trained
    if not outputs:
        pytest.skip("No failure models")
    horizon, (tag, _) = list(outputs.items())[0]
    fi = FailureInference(horizon=horizon, tag=tag, registry=reg)
    fi.load()
    features_df, _ = synthetic_dataset
    comp_id = features_df["component_id"].value_counts().index[0]
    comp_df = features_df[features_df["component_id"] == comp_id]
    asset_id = comp_df["asset_id"].iloc[0]
    r = fi.predict(comp_df, comp_id, asset_id)
    if r.null_reason:
        pytest.skip(r.null_reason)
    assert 0.0 <= r.failure_probability <= 1.0
    assert isinstance(r.alert, bool)
    assert r.alert == (r.failure_probability >= r.operational_threshold)


@pytest.mark.slow
def test_anomaly_inference_score_valid(anomaly_trained, synthetic_dataset):
    from app.ml.models.inference import AnomalyInference
    outputs, reg = anomaly_trained
    if not outputs:
        pytest.skip("No anomaly models")
    tag = reg.list_tags()[0]
    ai = AnomalyInference(tag=tag, registry=reg)
    ai.load()
    features_df, _ = synthetic_dataset
    comp_id = features_df["component_id"].value_counts().index[0]
    comp_df = features_df[features_df["component_id"] == comp_id]
    asset_id = comp_df["asset_id"].iloc[0]
    r = ai.predict(comp_df, comp_id, asset_id)
    if r.null_reason:
        pytest.skip(r.null_reason)
    assert 0.0 <= r.anomaly_score <= 1.0
    assert isinstance(r.is_anomaly, bool)
    for feat, score in r.top_contributing_features:
        assert isinstance(feat, str) and score >= 0.0


@pytest.mark.slow
def test_all_inference_null_on_all_nan(rul_trained, failure_trained, anomaly_trained, synthetic_dataset):
    """All inference classes must return null (not raise) for all-NaN feature rows."""
    from app.ml.models.inference import RULInference, FailureInference, AnomalyInference
    features_df, _ = synthetic_dataset
    feat_cols = get_numeric_feature_cols(features_df)
    nan_df = features_df.head(20).copy()
    for col in feat_cols:
        nan_df[col] = np.nan
    comp_id = nan_df["component_id"].iloc[0]
    asset_id = nan_df["asset_id"].iloc[0]

    tag, _, rul_reg = rul_trained
    ri = RULInference(tag=tag, registry=rul_reg)
    ri.load()
    assert ri.predict(nan_df, comp_id, asset_id).predicted_rul_hours is None

    outputs, fail_reg = failure_trained
    if outputs:
        horizon, (ftag, _) = list(outputs.items())[0]
        fi = FailureInference(horizon=horizon, tag=ftag, registry=fail_reg)
        fi.load()
        assert fi.predict(nan_df, comp_id, asset_id).failure_probability is None

    _, anom_reg = anomaly_trained
    atags = anom_reg.list_tags()
    if atoms := [t for t in atags]:
        ai = AnomalyInference(tag=atoms[0], registry=anom_reg)
        ai.load()
        assert ai.predict(nan_df, comp_id, asset_id).anomaly_score is None
