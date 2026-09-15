"""
FeaturePipeline — orchestrates all Phase 5 feature engineering steps.

Causal pipeline order (no future information enters at any step)
----------------------------------------------------------------
1. clean_telemetry()        — dedup, sort, clip to critical bounds
2. DataQualityDetector.flag() — attach quality_flag + quality_reason
3. compute_rolling_features() — rolling mean/std/min/max/slope/roc per sensor
4. compute_vibration_features() — vibration-specific (kurtosis, crest_factor, etc.)
5. compute_context_features()  — op-condition one-hots, maintenance recency, missions
6. _drop_non_feature_columns() — remove columns that are not ML inputs

The output of the pipeline is a feature DataFrame with NO truth columns.
Labels are generated SEPARATELY via LabelGenerator and kept separate.

Usage
-----
pipeline = FeaturePipeline(sensors_df)
features_df = pipeline.transform(
    telemetry_df, maintenance_df, missions_df
)
# features_df safe to use as model input

splitter = AssetTemporalSplitter(seed=42)
split = splitter.split(features_df, failure_events_df)
train_df, val_df, test_df = split.apply(features_df)

label_gen = LabelGenerator()
labels_df = label_gen.generate(health_trajectories_df, failure_events_df)
# Join labels only inside the training loop, not stored in features_df
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.ml.features.cleaning import clean_telemetry
from app.ml.features.context import compute_context_features
from app.ml.features.quality import DataQualityDetector, QualityFlag
from app.ml.features.rolling import DEFAULT_EWM_ALPHAS, DEFAULT_WINDOWS, compute_rolling_features
from app.ml.features.vibration import compute_vibration_features

# Columns retained from the raw telemetry as identity / join keys
# These are NOT model features but are needed to join labels later
_JOIN_KEY_COLUMNS: frozenset[str] = frozenset({
    "asset_id",
    "sensor_id",
    "component_id",
    "recorded_at",
})

# Columns from cleaning step that are identity but not features
_PASSTHROUGH_COLUMNS: frozenset[str] = frozenset({
    "operating_hours",
    "operating_condition",
    "is_clean",
    "quality_flag",
    "quality_reason",
    "source",
})

# Columns that must NEVER appear in the final feature matrix
FORBIDDEN_FEATURE_COLUMNS: frozenset[str] = frozenset({
    "value",          # raw value is replaced by rolling stats
    "true_health",
    "true_rul",
    "failure_timestamp",
    "failure_label",
    "failure_event",
    "archetype",
    "degradation_multiplier",
    "latent_health",
})


@dataclass
class FeatureCatalog:
    """Documents all features produced by the pipeline."""

    rolling_features: list[str] = field(default_factory=list)
    vibration_features: list[str] = field(default_factory=list)
    context_features: list[str] = field(default_factory=list)
    quality_features: list[str] = field(default_factory=list)

    @property
    def all_feature_names(self) -> list[str]:
        return (
            self.rolling_features
            + self.vibration_features
            + self.context_features
            + self.quality_features
        )

    def summary(self) -> str:
        return (
            f"FeatureCatalog: {len(self.all_feature_names)} total features\n"
            f"  rolling:    {len(self.rolling_features)}\n"
            f"  vibration:  {len(self.vibration_features)}\n"
            f"  context:    {len(self.context_features)}\n"
            f"  quality:    {len(self.quality_features)}"
        )


class FeaturePipeline:
    """Reusable feature pipeline for MissionReady telemetry.

    Parameters
    ----------
    sensors_df:
        Sensor metadata table (observable). Columns: sensor_id, sensor_type,
        critical_min, critical_max, nominal_min, nominal_max.
    windows:
        Rolling window sizes (in timesteps). Default: [6, 24, 72].
    ewm_alphas:
        EWM decay parameters. Default: [0.1, 0.3].
    quality_detector_kwargs:
        Extra kwargs forwarded to DataQualityDetector.
    """

    def __init__(
        self,
        sensors_df: pd.DataFrame,
        windows: list[int] = DEFAULT_WINDOWS,
        ewm_alphas: list[float] = DEFAULT_EWM_ALPHAS,
        **quality_detector_kwargs: object,
    ) -> None:
        self._sensors_df = sensors_df
        self._windows = windows
        self._ewm_alphas = ewm_alphas
        self._quality_detector = DataQualityDetector(
            sensors_df, **quality_detector_kwargs
        )

    def transform(
        self,
        telemetry_df: pd.DataFrame,
        maintenance_df: pd.DataFrame | None = None,
        missions_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Run the full feature pipeline on raw telemetry.

        Returns a feature DataFrame safe for use as model input.
        Join keys (asset_id, sensor_id, component_id, recorded_at) are
        preserved so labels can be joined at training time.
        """
        maint = maintenance_df if maintenance_df is not None else pd.DataFrame()
        missions = missions_df if missions_df is not None else pd.DataFrame()

        # 1. Clean
        df = clean_telemetry(telemetry_df, self._sensors_df)

        # 2. Quality flags
        df = self._quality_detector.flag(df)

        # 3. Rolling statistics
        df = compute_rolling_features(df, self._sensors_df, self._windows, self._ewm_alphas)

        # 4. Vibration features
        df = compute_vibration_features(df, self._sensors_df, self._windows)

        # 5. Context features
        df = compute_context_features(df, maint, missions)

        # 6. Remove forbidden columns (raw value, truth columns if somehow present)
        cols_to_drop = [c for c in df.columns if c in FORBIDDEN_FEATURE_COLUMNS]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)

        return df

    def feature_catalog(self, features_df: pd.DataFrame) -> FeatureCatalog:
        """Inspect a transformed DataFrame and return a FeatureCatalog."""
        from app.ml.features.rolling import _safe_col
        from app.ml.features.vibration import VIBRATION_SENSOR_TYPES

        # Derive expected sensor types
        if not self._sensors_df.empty and "sensor_type" in self._sensors_df.columns:
            sensor_types = self._sensors_df["sensor_type"].unique().tolist()
        else:
            sensor_types = []

        vib_prefixes = {
            _safe_col(st) for st in sensor_types if st in VIBRATION_SENSOR_TYPES
        }

        rolling_cols = []
        vibration_cols = []
        context_cols = []
        quality_cols = []

        non_feature = (
            _JOIN_KEY_COLUMNS
            | _PASSTHROUGH_COLUMNS
            | FORBIDDEN_FEATURE_COLUMNS
        )

        for col in features_df.columns:
            if col in non_feature:
                continue
            if col in ("quality_flag", "quality_reason", "is_clean"):
                quality_cols.append(col)
            elif col.startswith("op_cond_") or col.startswith("last_maint_") or col in (
                "hours_since_last_maint", "maint_event_count",
                "mission_active", "mission_criticality_max", "hours_until_next_mission",
            ):
                context_cols.append(col)
            elif any(col.startswith(f"{p}_vib_") or col.startswith(f"{p}_delta_")
                     for p in vib_prefixes):
                vibration_cols.append(col)
            elif "_roll" in col or "_ewm" in col:
                rolling_cols.append(col)

        return FeatureCatalog(
            rolling_features=sorted(rolling_cols),
            vibration_features=sorted(vibration_cols),
            context_features=sorted(context_cols),
            quality_features=sorted(quality_cols),
        )

    def validate_no_leakage(self, features_df: pd.DataFrame) -> list[str]:
        """Return list of leakage violations in the features DataFrame."""
        return [c for c in features_df.columns if c in FORBIDDEN_FEATURE_COLUMNS]


def build_feature_dataset(
    simulation_result: object,
    windows: list[int] = DEFAULT_WINDOWS,
    ewm_alphas: list[float] = DEFAULT_EWM_ALPHAS,
    **quality_kwargs: object,
) -> tuple[pd.DataFrame, pd.DataFrame, "FeatureCatalog"]:
    """Convenience function: run the full pipeline on a SimulationResult.

    Parameters
    ----------
    simulation_result:
        A ``SimulationResult`` from ``FleetSimulator.run()``.
    windows, ewm_alphas:
        Forwarded to FeaturePipeline.
    quality_kwargs:
        Forwarded to DataQualityDetector.

    Returns
    -------
    features_df:
        Full feature DataFrame (all assets, all timesteps).
        Join keys asset_id, sensor_id, component_id, recorded_at preserved.
        NO truth columns present.
    labels_df:
        Labels DataFrame from LabelGenerator.generate().
        Aligned on (component_id, timestamp).
        MUST be kept separate from features_df.
    catalog:
        FeatureCatalog describing all feature columns.
    """
    from app.ml.features.labels import LabelGenerator

    obs = simulation_result.observable
    truth = simulation_result.truth

    pipeline = FeaturePipeline(
        sensors_df=obs["sensors"],
        windows=windows,
        ewm_alphas=ewm_alphas,
        **quality_kwargs,
    )

    features_df = pipeline.transform(
        telemetry_df=obs["telemetry"],
        maintenance_df=obs.get("maintenance_events"),
        missions_df=obs.get("missions"),
    )

    label_gen = LabelGenerator()
    labels_df = label_gen.generate(
        health_trajectories=truth["component_health_trajectories"],
        failure_events=truth["failure_events"],
    )

    catalog = pipeline.feature_catalog(features_df)
    return features_df, labels_df, catalog
