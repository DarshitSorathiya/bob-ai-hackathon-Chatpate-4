"""
Phase 5 — Data Quality & Feature Engineering.

Public API
----------
from app.ml.features import (
    FeaturePipeline,
    DataQualityDetector,
    AssetTemporalSplitter,
    LabelGenerator,
    build_feature_dataset,
)
"""

from app.ml.features.pipeline import FeaturePipeline, build_feature_dataset
from app.ml.features.quality import DataQualityDetector, QualityFlag
from app.ml.features.split import AssetTemporalSplitter, DatasetSplit
from app.ml.features.labels import LabelGenerator

__all__ = [
    "FeaturePipeline",
    "build_feature_dataset",
    "DataQualityDetector",
    "QualityFlag",
    "AssetTemporalSplitter",
    "DatasetSplit",
    "LabelGenerator",
]
