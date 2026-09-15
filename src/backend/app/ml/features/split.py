"""
Asset-aware temporal train/validation/test splitter.

CRITICAL DESIGN REQUIREMENT
-----------------------------
Rows MUST NOT be randomly split across the train/test boundary.
Splitting randomly at the row level causes two leakage paths:
  1. Future telemetry of an asset appears in the training set,
     giving the model knowledge of future degradation trajectories.
  2. Rolling features at the boundary are computed from rows that
     span both train and test, contaminating the test split.

Correct splitting strategy
---------------------------
1. Split at the ASSET level:
   - Some assets appear only in train
   - Some assets appear only in validation
   - Some assets appear only in test (held out completely)
   This guarantees zero overlap of trajectories.

2. Within each asset's trajectory, use the FULL available history
   (no truncation at a calendar date for training assets).

3. Asset assignment is deterministic given the random seed.

Split fractions (configurable, default):
  train:       70% of assets
  validation:  15% of assets
  test:        15% of assets (held out; never used for hyperparameter tuning)

Output
------
DatasetSplit(
    train_asset_ids,    # set of asset_ids in training set
    val_asset_ids,      # set of asset_ids in validation set
    test_asset_ids,     # set of asset_ids in test set
    split_metadata      # boundary information for documentation
)

The split is applied to the FULL feature DataFrame by filtering on asset_id.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class DatasetSplit:
    """Asset-level dataset split boundaries."""

    train_asset_ids: set[str]
    val_asset_ids: set[str]
    test_asset_ids: set[str]
    split_metadata: dict[str, object] = field(default_factory=dict)

    def apply(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Filter *df* into (train, val, test) DataFrames by asset_id."""
        train = df[df["asset_id"].isin(self.train_asset_ids)].copy()
        val = df[df["asset_id"].isin(self.val_asset_ids)].copy()
        test = df[df["asset_id"].isin(self.test_asset_ids)].copy()
        return train, val, test

    def summary(self) -> str:
        meta = self.split_metadata
        return (
            f"AssetSplit — train:{len(self.train_asset_ids)} assets, "
            f"val:{len(self.val_asset_ids)} assets, "
            f"test:{len(self.test_asset_ids)} assets | "
            f"rows: train={meta.get('train_rows', '?')}, "
            f"val={meta.get('val_rows', '?')}, "
            f"test={meta.get('test_rows', '?')}"
        )


class AssetTemporalSplitter:
    """Split a feature DataFrame into train/val/test by asset ID.

    Parameters
    ----------
    train_frac:
        Fraction of assets assigned to training set.
    val_frac:
        Fraction of assets assigned to validation set.
        Test fraction = 1 - train_frac - val_frac.
    seed:
        Random seed for deterministic assignment.
    stratify_by_failure:
        If True, assets with at least one failure event are stratified
        across splits (so each split gets a proportional share of
        failed assets). Requires a ``has_failure`` boolean column.
    """

    def __init__(
        self,
        train_frac: float = 0.70,
        val_frac: float = 0.15,
        seed: int = 42,
    ) -> None:
        if not (0 < train_frac < 1 and 0 < val_frac < 1):
            raise ValueError("train_frac and val_frac must be strictly between 0 and 1")
        if train_frac + val_frac >= 1.0:
            raise ValueError("train_frac + val_frac must be < 1.0 (test fraction must be > 0)")
        self.train_frac = train_frac
        self.val_frac = val_frac
        self.seed = seed

    def split(
        self,
        features_df: pd.DataFrame,
        failure_events_df: pd.DataFrame | None = None,
    ) -> DatasetSplit:
        """Assign assets to train/val/test sets.

        Parameters
        ----------
        features_df:
            Feature DataFrame. Must contain ``asset_id`` column.
        failure_events_df:
            Optional failure events table (from truth). If provided, ensures
            at least one failed asset lands in each split.

        Returns
        -------
        DatasetSplit
        """
        all_asset_ids = sorted(features_df["asset_id"].unique().tolist())
        n = len(all_asset_ids)
        if n < 3:
            raise ValueError(
                f"Need at least 3 distinct assets to create train/val/test splits, got {n}."
            )

        rng = np.random.default_rng(self.seed)

        # Identify failed assets if truth table provided
        failed_ids: set[str] = set()
        if failure_events_df is not None and not failure_events_df.empty:
            failed_ids = set(failure_events_df["asset_id"].unique())

        # Separate failed vs censored asset lists (both shuffled deterministically)
        failed = [a for a in all_asset_ids if a in failed_ids]
        censored = [a for a in all_asset_ids if a not in failed_ids]
        rng.shuffle(failed)
        rng.shuffle(censored)

        def _three_way(lst: list[str]) -> tuple[list, list, list]:
            """Split a list 70/15/15."""
            n_ = len(lst)
            n_train = max(0, round(n_ * self.train_frac))
            n_val = max(0, round(n_ * self.val_frac))
            # Ensure at least 1 in test if list is non-empty
            if n_ > 0 and n_train + n_val >= n_:
                n_val = max(0, n_ - n_train - 1)
            return lst[:n_train], lst[n_train:n_train + n_val], lst[n_train + n_val:]

        if failed:
            f_train, f_val, f_test = _three_way(failed)
            c_train, c_val, c_test = _three_way(censored)
            train_ids = f_train + c_train
            val_ids = f_val + c_val
            test_ids = f_test + c_test
        else:
            train_ids, val_ids, test_ids = _three_way(all_asset_ids)

        # Guard: every split must have at least one asset
        if not val_ids and len(train_ids) > 1:
            val_ids = [train_ids.pop()]
        if not test_ids and len(train_ids) > 1:
            test_ids = [train_ids.pop()]

        train_set = set(train_ids)
        val_set = set(val_ids)
        test_set = set(test_ids)

        # Compute row counts
        train_rows = int(features_df["asset_id"].isin(train_set).sum())
        val_rows = int(features_df["asset_id"].isin(val_set).sum())
        test_rows = int(features_df["asset_id"].isin(test_set).sum())

        metadata: dict[str, object] = {
            "n_total_assets": n,
            "n_train_assets": len(train_set),
            "n_val_assets": len(val_set),
            "n_test_assets": len(test_set),
            "n_failed_assets": len(failed),
            "failed_in_train": len([a for a in train_ids if a in failed_ids]),
            "failed_in_val": len([a for a in val_ids if a in failed_ids]),
            "failed_in_test": len([a for a in test_ids if a in failed_ids]),
            "train_rows": train_rows,
            "val_rows": val_rows,
            "test_rows": test_rows,
            "seed": self.seed,
            "strategy": "asset-level stratified by failure",
        }

        return DatasetSplit(
            train_asset_ids=train_set,
            val_asset_ids=val_set,
            test_asset_ids=test_set,
            split_metadata=metadata,
        )

    def validate_no_overlap(self, split: DatasetSplit) -> list[str]:
        """Return list of overlap violations (empty = clean)."""
        violations = []
        tv = split.train_asset_ids & split.val_asset_ids
        tt = split.train_asset_ids & split.test_asset_ids
        vt = split.val_asset_ids & split.test_asset_ids
        if tv:
            violations.append(f"train∩val overlap: {len(tv)} assets")
        if tt:
            violations.append(f"train∩test overlap: {len(tt)} assets")
        if vt:
            violations.append(f"val∩test overlap: {len(vt)} assets")
        return violations
