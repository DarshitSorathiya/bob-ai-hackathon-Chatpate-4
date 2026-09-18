#!/usr/bin/env python3
"""Train all MissionReady ML models from reproducible synthetic data.

The simulator is the canonical schema for deployment features. When processed
NASA CMAPSS or IMS files exist, their measured features and labels are adapted
into the same component/timestamp contract and included in training. This
keeps the deployed inference path identical to the simulator path while still
using real source distributions during training.

Examples (from the repository root):
    .venv\\Scripts\\python.exe src/backend/scripts/train_from_synthetic.py
    .venv\\Scripts\\python.exe src/backend/scripts/train_from_synthetic.py \\
        --assets-per-shard 30 --shards 4 --days 365 --seed 42

Prerequisites for source fusion:
    python src/backend/scripts/download_datasets.py --dataset cmapss
    python src/backend/scripts/preprocess_cmapss.py --subset all --no-checksums
    # IMS requires the raw NASA files; then run preprocess_ims.py.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.ml.features import build_feature_dataset
from app.ml.models.inference import AnomalyInference, FailureInference, RULInference
from app.ml.models.registry import ModelRegistry
from app.ml.simulator import FleetSimulator
from app.ml.simulator.config import default_config
from app.ml.training import AnomalyTrainer, FailureTrainer, RULTrainer
from app.ml.training.utils import get_numeric_feature_cols

LOG = logging.getLogger("train_from_synthetic")
PROCESSED_ROOT = BACKEND_ROOT / "data" / "processed"
DATASET_ROOT = BACKEND_ROOT / "data" / "training"


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _read_parquet_files(paths: Iterable[Path]) -> pd.DataFrame | None:
    frames = []
    for path in paths:
        if path.exists():
            LOG.info("Loading %s", path)
            frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True) if frames else None


def _normalise_timestamp(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.isoformat()


def _source_labels(
    source: str,
    features: pd.DataFrame,
    labels: pd.DataFrame | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return RUL and failure labels aligned to source feature row order."""
    labels = labels.reset_index(drop=True) if labels is not None else pd.DataFrame()
    features = features.reset_index(drop=True)

    if source == "cmapss":
        if "true_rul" in labels:
            rul = labels["true_rul"].to_numpy(dtype=float)
        elif "rul_cycles" in labels:
            rul = labels["rul_cycles"].to_numpy(dtype=float)
        else:
            rul = (
                features.groupby("unit_id")["cycle"].transform("max") - features["cycle"]
            ).to_numpy(dtype=float)
        if len(rul) != len(features):
            rul = (
                features.groupby("unit_id")["cycle"].transform("max") - features["cycle"]
            ).to_numpy(dtype=float)
        failure = (rul <= 72.0).astype(int)
        return rul, failure

    failure_column = "failure_label" if "failure_label" in labels else None
    failure = labels[failure_column].to_numpy(dtype=int) if failure_column else np.zeros(len(features), dtype=int)
    if len(failure) != len(features):
        failure = np.zeros(len(features), dtype=int)
    if "snapshot_index" in features:
        rul = features.groupby(["run_id", "bearing_id"])["snapshot_index"].transform("max") - features["snapshot_index"]
    else:
        rul = pd.Series(np.arange(len(features), 0, -1), dtype=float)
    return rul.to_numpy(dtype=float), failure


def adapt_reference_source(
    source: str,
    features: pd.DataFrame,
    labels: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Adapt CMAPSS or IMS rows to the shared trainer feature/label schema."""
    features = features.reset_index(drop=True).copy()
    rul, failure = _source_labels(source, features, labels)
    numeric_columns = features.select_dtypes(include=[np.number]).columns.tolist()
    ignored = {"unit_id", "cycle", "snapshot_index", "bearing_id", "failure_label", "true_rul", "rul_cycles"}
    numeric_columns = [column for column in numeric_columns if column not in ignored]

    if source == "cmapss":
        group_values = features["unit_id"].astype(str)
        row_numbers = features.groupby("unit_id").cumcount()
        component_type = "ENGINE_CORE"
    else:
        group_values = features["run_id"].astype(str) + "-" + features["bearing_id"].astype(str)
        row_numbers = features.groupby(["run_id", "bearing_id"]).cumcount()
        component_type = "BEARING"

    component_ids = group_values.map(lambda value: f"{source.upper()}-{value}-COMP")
    asset_ids = group_values.map(lambda value: f"{source.upper()}-{value}")
    timestamps = [
        _normalise_timestamp(pd.Timestamp("2020-01-01", tz="UTC") + pd.Timedelta(hours=int(step)))
        for step in row_numbers
    ]

    adapted = pd.DataFrame({
        "asset_id": asset_ids,
        "component_id": component_ids,
        "sensor_id": component_ids + "-SENSOR",
        "recorded_at": timestamps,
        "operating_hours": row_numbers.astype(float),
        "operating_condition": "SOURCE_REFERENCE",
        "source": source,
    })
    for column in numeric_columns:
        adapted[f"reference_{source}_{column}"] = pd.to_numeric(features[column], errors="coerce").astype(float)

    labels_out = pd.DataFrame({
        "asset_id": asset_ids,
        "component_id": component_ids,
        "timestamp": timestamps,
        "rul_cycles": np.clip(rul, 0.0, 3000.0),
        "failure_within_24h": (rul <= 24.0).astype(int),
        "failure_within_72h": (rul <= 72.0).astype(int),
        "failure_within_window": failure.astype(int),
        "health_class": np.where(rul > 72.0, "HEALTHY", "CRITICAL"),
    })
    components = pd.DataFrame({
        "component_id": component_ids.drop_duplicates().values,
        "asset_id": asset_ids.drop_duplicates().values,
        "component_type": component_type,
    })
    return adapted, labels_out, components


def load_processed_references() -> tuple[list[pd.DataFrame], list[pd.DataFrame], list[pd.DataFrame]]:
    """Load all available processed CMAPSS and IMS datasets."""
    feature_frames: list[pd.DataFrame] = []
    label_frames: list[pd.DataFrame] = []
    component_frames: list[pd.DataFrame] = []

    cmapss_features = sorted((PROCESSED_ROOT / "cmapss").glob("*_train_features.parquet"))
    for feature_path in cmapss_features:
        label_path = feature_path.with_name(feature_path.name.replace("_features", "_labels"))
        features = pd.read_parquet(feature_path)
        labels = pd.read_parquet(label_path) if label_path.exists() else None
        adapted_features, adapted_labels, components = adapt_reference_source("cmapss", features, labels)
        feature_frames.append(adapted_features)
        label_frames.append(adapted_labels)
        component_frames.append(components)

    ims_features_path = PROCESSED_ROOT / "ims" / "ims_features.parquet"
    ims_labels_path = PROCESSED_ROOT / "ims" / "ims_labels.parquet"
    if ims_features_path.exists():
        features = pd.read_parquet(ims_features_path)
        labels = pd.read_parquet(ims_labels_path) if ims_labels_path.exists() else None
        adapted_features, adapted_labels, components = adapt_reference_source("ims", features, labels)
        feature_frames.append(adapted_features)
        label_frames.append(adapted_labels)
        component_frames.append(components)

    return feature_frames, label_frames, component_frames


def generate_simulator_training_data(
    shards: int,
    assets_per_shard: int,
    days: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, list[str]], pd.DataFrame]:
    feature_frames = []
    label_frames = []
    component_frames = []
    failure_frames = []
    edge_case_tags: dict[str, list[str]] = {}
    last_result = None

    for shard in range(shards):
        shard_seed = seed + shard
        LOG.info("Simulating shard %d/%d: assets=%d days=%d seed=%d", shard + 1, shards, assets_per_shard, days, shard_seed)
        result = FleetSimulator(default_config(
            n_assets=assets_per_shard,
            sim_days=days,
            seed=shard_seed,
            timestep_hours=1.0,
        )).run()
        features, labels, _ = build_feature_dataset(result)
        feature_frames.append(features)
        label_frames.append(labels)
        component_frames.append(result.observable["components"])
        failure_frames.append(result.truth["failure_events"])
        edge_case_tags.update(result.edge_case_tags)
        last_result = result

    assert last_result is not None
    return (
        pd.concat(feature_frames, ignore_index=True),
        pd.concat(label_frames, ignore_index=True),
        pd.concat(component_frames, ignore_index=True).drop_duplicates("component_id"),
        pd.concat(failure_frames, ignore_index=True),
        edge_case_tags,
        last_result.observable["components"],
    )


def train(args: argparse.Namespace) -> dict[str, object]:
    if args.shards * args.assets_per_shard < 3:
        raise ValueError("The training set must contain at least 3 assets for temporal train/val/test splits")

    features, labels, components, failure_events, edge_case_tags, _ = generate_simulator_training_data(
        args.shards, args.assets_per_shard, args.days, args.seed
    )
    LOG.info("Simulator data ready: %d rows, %d components", len(features), features["component_id"].nunique())

    reference_features, reference_labels, reference_components = load_processed_references()
    if reference_features:
        LOG.info("Adding %d processed CMAPSS/IMS reference rows", sum(len(frame) for frame in reference_features))
        features = pd.concat([features, *reference_features], ignore_index=True, sort=False)
        labels = pd.concat([labels, *reference_labels], ignore_index=True, sort=False)
        components = pd.concat([components, *reference_components], ignore_index=True, sort=False).drop_duplicates("component_id")
    else:
        LOG.warning("No processed CMAPSS/IMS data found; training uses simulator data only")
        if args.require_references:
            raise FileNotFoundError(
                "Processed CMAPSS/IMS data is required. Run the download and preprocessing commands first."
            )

    DATASET_ROOT.mkdir(parents=True, exist_ok=True)
    features_path = DATASET_ROOT / "synthetic_features.parquet"
    labels_path = DATASET_ROOT / "synthetic_labels.parquet"
    features.to_parquet(features_path, index=False)
    labels.to_parquet(labels_path, index=False)
    LOG.info("Saved %d feature rows and %d label rows", len(features), len(labels))

    registry = ModelRegistry()
    LOG.info("Training RUL candidates")
    rul_tag, rul_results = RULTrainer(seed=args.seed, registry=registry).train(
        features, labels, failure_events_df=failure_events, tag_prefix="rul"
    )
    LOG.info("Registered RUL model: %s", rul_tag)
    LOG.info("Training failure-risk candidates")
    failure_results = FailureTrainer(seed=args.seed, registry=registry).train(
        features, labels, failure_events_df=failure_events, tag_prefix="failure"
    )
    LOG.info("Registered failure models: %s", list(failure_results))
    LOG.info("Training anomaly candidates")
    anomaly_results = AnomalyTrainer(seed=args.seed, registry=registry).train(
        features, components, edge_case_tags=edge_case_tags, tag_prefix="anomaly"
    )
    LOG.info("Registered anomaly models: %s", list(anomaly_results))

    simulator_component = components.iloc[0]
    component_id = str(simulator_component["component_id"])
    asset_id = str(simulator_component["asset_id"])
    component_features = features[features["component_id"] == component_id]
    predictions: dict[str, object] = {
        "component_id": component_id,
        "asset_id": asset_id,
    }
    predictions["rul"] = RULInference(tag=rul_tag, registry=registry).predict(component_features, component_id, asset_id).__dict__
    if "24h" in failure_results:
        predictions["failure_24h"] = FailureInference(horizon="24h", registry=registry).predict(component_features, component_id, asset_id).__dict__
    component_type = str(simulator_component.get("component_type", ""))
    if component_type in anomaly_results:
        predictions["anomaly"] = AnomalyInference(component_type=component_type, registry=registry).predict(component_features, component_id, asset_id).__dict__

    summary = {
        "rows": len(features),
        "components": int(features["component_id"].nunique()),
        "numeric_features": len(get_numeric_feature_cols(features)),
        "rul_tag": rul_tag,
        "failure_tags": {horizon: result[0] for horizon, result in failure_results.items()},
        "anomaly_tags": {component_type: result[0] for component_type, result in anomaly_results.items()},
        "dataset_features": str(features_path),
        "dataset_labels": str(labels_path),
        "predictions": predictions,
    }
    summary_path = DATASET_ROOT / "training_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    LOG.info("Training complete. Summary: %s", summary_path)
    print(json.dumps(summary, indent=2, default=str))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic data and train/register all MissionReady models")
    parser.add_argument("--shards", type=int, default=2, help="Independent simulator runs to combine")
    parser.add_argument("--assets-per-shard", type=int, default=25, help="Assets per simulator run")
    parser.add_argument("--days", type=int, default=365, help="Simulated days per shard")
    parser.add_argument("--seed", type=int, default=42, help="Base random seed")
    parser.add_argument("--require-references", action="store_true", help="Fail unless processed CMAPSS or IMS data is available")
    args = parser.parse_args()
    _configure_logging()
    train(args)


if __name__ == "__main__":
    main()
