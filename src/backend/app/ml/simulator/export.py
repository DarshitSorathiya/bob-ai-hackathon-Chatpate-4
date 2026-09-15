"""
Anti-leakage export layer — separates simulator truth from observable data.

STRICT CONTRACT
---------------
observable_data keys:
  assets, components, sensors, telemetry, data_quality_events,
  maintenance_events, missions

  These DataFrames MUST NOT contain:
    - true_health
    - true_rul
    - failure_timestamp
    - failure_type (of the truth variety)
    - degradation_multiplier
    - archetype
    - any column prefixed "truth_" or "latent_"

truth_data keys:
  component_health_trajectories   (component_id, asset_id, step, timestamp, health, true_rul)
  failure_events                  (component_id, asset_id, failure_timestamp, failure_type)
  asset_truths                    (asset_id, archetype per component, degradation_multiplier)

  truth_data is ONLY used for label generation and simulator validation.
  It is NEVER passed to the ML feature pipeline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.ml.simulator.config import SimulatorConfig
from app.ml.simulator.edge_cases import EdgeCaseInjectionPlan, EdgeCaseTag
from app.ml.simulator.truth import FleetTruth


# Columns that are NEVER allowed in observable DataFrames
FORBIDDEN_OBSERVABLE_COLUMNS = frozenset({
    "true_health",
    "true_rul",
    "failure_timestamp",
    "latent_health",
    "degradation_multiplier",
    "archetype",
    "failure_type",
    "health",
})


@dataclass
class SimulationResult:
    """Complete simulator output, split into observable and truth layers."""

    observable: dict[str, pd.DataFrame]
    """ML-visible tables — safe to use as model input/features."""

    truth: dict[str, pd.DataFrame]
    """Ground-truth tables — labels only, never model input."""

    edge_case_tags: dict[str, list[str]]
    """Maps asset_id → list of EdgeCaseTag values applied to that asset."""

    config_summary: dict[str, Any]
    """Snapshot of key configuration parameters."""

    def summary(self) -> dict[str, Any]:
        return {
            "observable_tables": {k: len(v) for k, v in self.observable.items()},
            "truth_tables": {k: len(v) for k, v in self.truth.items()},
            "n_failed_components": len(self.truth.get("failure_events", pd.DataFrame())),
            "edge_case_asset_count": len(self.edge_case_tags),
            "config": self.config_summary,
        }

    def validate_no_leakage(self) -> list[str]:
        """Return list of violations (empty = clean)."""
        violations = []
        for table_name, df in self.observable.items():
            for col in FORBIDDEN_OBSERVABLE_COLUMNS:
                if col in df.columns:
                    violations.append(
                        f"observable['{table_name}'] contains forbidden column '{col}'"
                    )
        return violations


def build_result(
    asset_rows: list[dict],
    component_rows: list[dict],
    sensor_rows: list[dict],
    telemetry_rows: list[dict],
    dq_rows: list[dict],
    maintenance_rows: list[dict],
    mission_rows: list[dict],
    fleet_truth: FleetTruth,
    plan: EdgeCaseInjectionPlan,
    cfg: SimulatorConfig,
) -> SimulationResult:
    """Assemble SimulationResult from raw row lists, enforcing leakage boundaries."""

    # --- Observable DataFrames -------------------------------------------
    assets_df = pd.DataFrame(asset_rows) if asset_rows else _empty_assets()
    components_df = _make_components_df(component_rows)
    sensors_df = pd.DataFrame(sensor_rows) if sensor_rows else _empty_sensors()
    telemetry_df = pd.DataFrame(telemetry_rows) if telemetry_rows else _empty_telemetry()
    dq_df = pd.DataFrame(dq_rows) if dq_rows else _empty_dq()
    maintenance_df = pd.DataFrame(maintenance_rows) if maintenance_rows else _empty_maintenance()
    missions_df = pd.DataFrame(mission_rows) if mission_rows else _empty_missions()

    # Enforce: no forbidden columns leak into observable tables
    for name, df in [
        ("assets", assets_df),
        ("components", components_df),
        ("telemetry", telemetry_df),
    ]:
        for col in FORBIDDEN_OBSERVABLE_COLUMNS:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

    observable = {
        "assets": assets_df,
        "components": components_df,
        "sensors": sensors_df,
        "telemetry": telemetry_df,
        "data_quality_events": dq_df,
        "maintenance_events": maintenance_df,
        "missions": missions_df,
    }

    # --- Truth DataFrames ------------------------------------------------
    health_rows = []
    failure_rows = []
    for at in fleet_truth.asset_truths.values():
        for ct in at.component_truths.values():
            for i, ts in enumerate(ct.timestamps):
                health_rows.append({
                    "component_id": ct.component_id,
                    "asset_id": ct.asset_id,
                    "step": i,
                    "timestamp": ts.isoformat(),
                    "true_health": ct.health[i],
                    "true_rul": ct.true_rul[i] if ct.true_rul else None,
                })
            if ct.failure_timestamp is not None:
                import hashlib as _hl
                _fk = f"{ct.component_id}:{ct.failure_timestamp.isoformat()}"
                _fh = _hl.sha256(_fk.encode()).hexdigest()
                _feid = f"{_fh[:8]}-{_fh[8:12]}-{_fh[12:16]}-{_fh[16:20]}-{_fh[20:32]}"
                failure_rows.append({
                    "event_id": _feid,
                    "asset_id": ct.asset_id,
                    "component_id": ct.component_id,
                    "failure_type": ct.failure_type or "UNKNOWN",
                    "severity": "CRITICAL",
                    "occurred_at": ct.failure_timestamp.isoformat(),
                    "source": "simulator",
                })

    truth = {
        "component_health_trajectories": pd.DataFrame(health_rows) if health_rows
            else _empty_health_traj(),
        "failure_events": pd.DataFrame(failure_rows) if failure_rows
            else _empty_failure_events(),
    }

    # --- Edge case tags map -----------------------------------------------
    edge_case_tags = {
        asset_id: [tag.value for tag in tags]
        for asset_id, tags in plan.asset_tags.items()
    }

    # --- Config summary ---------------------------------------------------
    config_summary = {
        "profile_name": cfg.profile.name,
        "n_assets": cfg.profile.n_assets,
        "sim_days": cfg.profile.sim_days,
        "timestep_hours": cfg.profile.timestep_hours,
        "seed": cfg.profile.seed,
    }

    return SimulationResult(
        observable=observable,
        truth=truth,
        edge_case_tags=edge_case_tags,
        config_summary=config_summary,
    )


# ─── Schema helpers for empty DataFrames ──────────────────────────────────────


def _make_components_df(rows: list[dict]) -> pd.DataFrame:
    """Build components DataFrame, stripping truth-only columns."""
    if not rows:
        return _empty_components()
    df = pd.DataFrame(rows)
    # archetype is in truth layer only
    if "archetype" in df.columns:
        df = df.drop(columns=["archetype"])
    return df


def _empty_assets() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "asset_id", "asset_code", "asset_type", "commission_date",
        "total_hours", "is_active", "usage_intensity", "sensor_quality",
    ])


def _empty_components() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "component_id", "asset_id", "component_code", "component_type",
        "name", "mtbf_hours", "is_active",
    ])


def _empty_sensors() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "sensor_id", "component_id", "asset_id", "sensor_code",
        "sensor_type", "unit", "nominal_min", "nominal_max",
        "critical_min", "critical_max", "is_active",
    ])


def _empty_telemetry() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "asset_id", "sensor_id", "component_id", "value",
        "recorded_at", "operating_hours", "operating_condition", "source",
    ])


def _empty_dq() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "event_id", "asset_id", "sensor_id", "event_type",
        "severity", "description", "started_at", "is_active",
    ])


def _empty_maintenance() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "event_id", "asset_id", "component_id", "event_type",
        "performed_at", "asset_hours_at_event", "description",
    ])


def _empty_missions() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "mission_id", "mission_code", "asset_id", "name",
        "criticality", "scheduled_start", "duration_hours", "status",
        "role", "is_conflict",
    ])


def _empty_health_traj() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "component_id", "asset_id", "step", "timestamp",
        "true_health", "true_rul",
    ])


def _empty_failure_events() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "event_id", "asset_id", "component_id", "failure_type",
        "severity", "occurred_at", "source",
    ])
