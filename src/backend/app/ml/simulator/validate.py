"""
Simulator validation suite.

Runs a series of checks on a SimulationResult to verify:
  1. Referential integrity between observable tables
  2. Timestamp monotonicity (per sensor)
  3. Value distributions within physical bounds
  4. Degradation progression before failures
  5. Maintenance recovery effects
  6. Edge case presence
  7. Label correctness (failure events match truth trajectories)
  8. Leakage boundaries (no forbidden columns in observable)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.ml.simulator.edge_cases import EdgeCaseTag
from app.ml.simulator.export import FORBIDDEN_OBSERVABLE_COLUMNS, SimulationResult

log = logging.getLogger(__name__)

# Physical bounds for sensor sanity checks
SENSOR_BOUNDS: dict[str, tuple[float, float]] = {
    "VIBRATION_RMS":    (0.0, 25.0),
    "TEMP_ENGINE":      (-40.0, 400.0),
    "PRESSURE_HYD":     (0.0, 6000.0),
    "FAN_SPEED_RPM":    (0.0, 25000.0),
    "BEARING_VIBRATION":(0.0, 30.0),
    "BEARING_TEMP":     (-40.0, 300.0),
    "OIL_PRESSURE":     (0.0, 200.0),
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        lines = [
            f"{'PASS' if self.passed else 'FAIL'} — "
            f"Simulator validation: {ok}/{total} checks passed"
        ]
        for r in self.results:
            icon = "✓" if r.passed else "✗"
            lines.append(f"  {icon} {r.name}: {r.details}")
            for w in r.warnings:
                lines.append(f"    ⚠ {w}")
        return "\n".join(lines)

    def raise_if_failed(self) -> None:
        if not self.passed:
            failures = [r for r in self.results if not r.passed]
            msg = "\n".join(f"  {r.name}: {r.details}" for r in failures)
            raise ValueError(f"Simulator validation FAILED:\n{msg}")


def validate_simulation(result: SimulationResult) -> ValidationReport:
    """Run the full validation suite on a SimulationResult."""
    report = ValidationReport()

    report.add(_check_leakage(result))
    report.add(_check_referential_integrity(result))
    report.add(_check_timestamp_monotonicity(result))
    report.add(_check_value_distributions(result))
    report.add(_check_degradation_progression(result))
    report.add(_check_maintenance_recovery(result))
    report.add(_check_edge_cases(result))
    report.add(_check_label_correctness(result))
    report.add(_check_censored_no_failure(result))

    return report


# ─── Individual checks ────────────────────────────────────────────────────────


def _check_leakage(result: SimulationResult) -> CheckResult:
    """Verify no forbidden columns exist in observable DataFrames."""
    violations = result.validate_no_leakage()
    if violations:
        return CheckResult(
            name="leakage_guard",
            passed=False,
            details=f"{len(violations)} leakage violation(s): {violations[:3]}",
        )
    return CheckResult(
        name="leakage_guard",
        passed=True,
        details="No forbidden columns in observable tables",
    )


def _check_referential_integrity(result: SimulationResult) -> CheckResult:
    """Verify FK relationships between observable tables."""
    obs = result.observable
    violations = []

    assets_df = obs.get("assets", pd.DataFrame())
    comps_df = obs.get("components", pd.DataFrame())
    sensors_df = obs.get("sensors", pd.DataFrame())
    tel_df = obs.get("telemetry", pd.DataFrame())
    maint_df = obs.get("maintenance_events", pd.DataFrame())
    missions_df = obs.get("missions", pd.DataFrame())

    if assets_df.empty:
        return CheckResult(name="referential_integrity", passed=False,
                           details="No assets generated")

    asset_ids = set(assets_df["asset_id"].tolist())
    comp_ids = set(comps_df["component_id"].tolist()) if not comps_df.empty else set()
    sensor_ids = set(sensors_df["sensor_id"].tolist()) if not sensors_df.empty else set()

    # components → assets
    if not comps_df.empty:
        bad = set(comps_df["asset_id"]) - asset_ids
        if bad:
            violations.append(f"components: {len(bad)} unknown asset_ids")

    # sensors → components
    if not sensors_df.empty:
        bad = set(sensors_df["component_id"]) - comp_ids
        if bad:
            violations.append(f"sensors: {len(bad)} unknown component_ids")

    # telemetry → assets/sensors/components
    if not tel_df.empty:
        bad = set(tel_df["asset_id"]) - asset_ids
        if bad:
            violations.append(f"telemetry: {len(bad)} unknown asset_ids")
        bad = set(tel_df["sensor_id"]) - sensor_ids
        if bad:
            violations.append(f"telemetry: {len(bad)} unknown sensor_ids")

    # maintenance → assets
    if not maint_df.empty:
        bad = set(maint_df["asset_id"]) - asset_ids
        if bad:
            violations.append(f"maintenance_events: {len(bad)} unknown asset_ids")

    # missions → assets
    if not missions_df.empty:
        bad = set(missions_df["asset_id"]) - asset_ids
        if bad:
            violations.append(f"missions: {len(bad)} unknown asset_ids")

    if violations:
        return CheckResult(
            name="referential_integrity",
            passed=False,
            details="; ".join(violations),
        )
    return CheckResult(
        name="referential_integrity",
        passed=True,
        details=f"{len(asset_ids)} assets, {len(comp_ids)} components, "
                f"{len(sensor_ids)} sensors — all FK relationships valid",
    )


def _check_timestamp_monotonicity(result: SimulationResult) -> CheckResult:
    """Verify timestamps are non-decreasing per (asset, sensor) stream.

    Duplicate timestamps are allowed (DUPLICATE_TIMESTAMP edge case).
    """
    tel = result.observable.get("telemetry", pd.DataFrame())
    if tel.empty:
        return CheckResult(name="timestamp_monotonicity", passed=True,
                           details="No telemetry rows")

    tel = tel.copy()
    tel["recorded_at_dt"] = pd.to_datetime(tel["recorded_at"])
    violations = 0

    for (asset_id, sensor_id), group in tel.groupby(["asset_id", "sensor_id"], sort=False):
        ts = group["recorded_at_dt"].values
        if len(ts) < 2:
            continue
        # Allow duplicates; only flag backwards time
        diffs = np.diff(ts.astype("int64"))
        if (diffs < 0).any():
            violations += 1

    if violations > 0:
        return CheckResult(
            name="timestamp_monotonicity",
            passed=False,
            details=f"{violations} sensor streams have backwards timestamps",
        )
    return CheckResult(
        name="timestamp_monotonicity",
        passed=True,
        details="All sensor time series are non-decreasing",
    )


def _check_value_distributions(result: SimulationResult) -> CheckResult:
    """Check sensor values are within physical bounds."""
    tel = result.observable.get("telemetry", pd.DataFrame())
    sensors = result.observable.get("sensors", pd.DataFrame())

    if tel.empty or sensors.empty:
        return CheckResult(name="value_distributions", passed=True, details="No telemetry")

    merged = tel.merge(sensors[["sensor_id", "sensor_type"]], on="sensor_id", how="left")
    violations = []
    warnings = []

    for stype, (lo, hi) in SENSOR_BOUNDS.items():
        sub = merged[merged["sensor_type"] == stype]
        if sub.empty:
            continue
        out_of_range = ((sub["value"] < lo) | (sub["value"] > hi)).sum()
        if out_of_range > 0:
            frac = out_of_range / len(sub)
            if frac > 0.01:
                violations.append(f"{stype}: {out_of_range} out-of-range values ({frac:.1%})")
            else:
                warnings.append(f"{stype}: {out_of_range} minor out-of-range")

    if violations:
        return CheckResult(
            name="value_distributions",
            passed=False,
            details="; ".join(violations),
            warnings=warnings,
        )
    return CheckResult(
        name="value_distributions",
        passed=True,
        details="All sensor values within physical bounds",
        warnings=warnings,
    )


def _check_degradation_progression(result: SimulationResult) -> CheckResult:
    """Verify that assets with failure events had declining health before failure."""
    failures = result.truth.get("failure_events", pd.DataFrame())
    health = result.truth.get("component_health_trajectories", pd.DataFrame())

    if failures.empty:
        return CheckResult(
            name="degradation_progression",
            passed=True,
            details="No failures to check (all censored)",
            warnings=["0 failures in this run — increase sim_days or assets"],
        )

    violations = 0
    checked = 0

    for _, row in failures.iterrows():
        cid = row["component_id"]
        traj = health[health["component_id"] == cid].sort_values("step")
        if traj.empty or len(traj) < 10:
            continue

        checked += 1
        n = len(traj)
        # Use median of first 30% vs last 30% — robust to the high_anomaly_low_failure
        # edge case which causes a temporary dip then recovery before final decline.
        first_median = traj["true_health"].iloc[:max(1, n * 3 // 10)].median()
        last_median = traj["true_health"].iloc[max(1, n * 7 // 10):].median()

        # Allow 5% tolerance for abrupt / dip-recovery archetypes
        if first_median < last_median - 0.05:
            violations += 1
            log.debug(
                "Degradation check: component %s — first30p=%.3f, last30p=%.3f",
                cid[:8], first_median, last_median,
            )

    if violations > 0:
        return CheckResult(
            name="degradation_progression",
            passed=False,
            details=f"{violations}/{checked} failed components had non-monotonic health",
        )
    return CheckResult(
        name="degradation_progression",
        passed=True,
        details=f"{checked} failed components verified — health declined before failure",
    )


def _check_maintenance_recovery(result: SimulationResult) -> CheckResult:
    """Check that post-maintenance health is higher than pre-maintenance health."""
    health = result.truth.get("component_health_trajectories", pd.DataFrame())
    maint = result.observable.get("maintenance_events", pd.DataFrame())

    if maint.empty:
        return CheckResult(
            name="maintenance_recovery",
            passed=True,
            details="No maintenance events to check",
            warnings=["No maintenance events generated"],
        )

    if health.empty:
        return CheckResult(name="maintenance_recovery", passed=True,
                           details="No health trajectories")

    passed_count = 0
    failed_count = 0

    for _, row in maint.iterrows():
        cid = row.get("component_id")
        if not cid:
            continue
        maint_time = row["performed_at"]
        traj = health[health["component_id"] == cid].sort_values("step")
        if len(traj) < 10:
            continue

        traj_ts = pd.to_datetime(traj["timestamp"])
        pre_mask = traj_ts < pd.Timestamp(maint_time)
        post_mask = traj_ts > pd.Timestamp(maint_time)

        pre = traj[pre_mask]["true_health"].tail(5).mean()
        post = traj[post_mask]["true_health"].head(5).mean()

        if not (np.isnan(pre) or np.isnan(post)):
            if post >= pre - 0.05:  # 5% tolerance for timing
                passed_count += 1
            else:
                failed_count += 1

    if failed_count > passed_count * 0.2 and failed_count > 2:
        return CheckResult(
            name="maintenance_recovery",
            passed=False,
            details=f"{failed_count} maintenance events did not restore health",
        )
    return CheckResult(
        name="maintenance_recovery",
        passed=True,
        details=f"{passed_count} verified, {failed_count} marginal",
    )


def _check_edge_cases(result: SimulationResult) -> CheckResult:
    """Verify that each enabled edge case type is present in the output."""
    dq = result.observable.get("data_quality_events", pd.DataFrame())
    missions = result.observable.get("missions", pd.DataFrame())
    maint = result.observable.get("maintenance_events", pd.DataFrame())
    tel = result.observable.get("telemetry", pd.DataFrame())
    all_tags: set[str] = set()
    for tags in result.edge_case_tags.values():
        all_tags.update(tags)

    missing = []

    # Check observable evidence for each expected tag
    if EdgeCaseTag.MISSING_TELEMETRY.value in all_tags:
        # Evidence: some sensors have fewer rows than others (gap)
        if not tel.empty:
            counts = tel.groupby("sensor_id").size()
            if counts.std() < 1.0:
                missing.append("missing_telemetry: no gap detected")

    if EdgeCaseTag.DUPLICATE_TIMESTAMP.value in all_tags:
        if not tel.empty:
            dup = tel.duplicated(subset=["sensor_id", "recorded_at"])
            if not dup.any():
                missing.append("duplicate_timestamp: no duplicates found")

    if EdgeCaseTag.SENSOR_FAILURE.value in all_tags or \
       EdgeCaseTag.STUCK_SENSOR.value in all_tags or \
       EdgeCaseTag.STALE_TELEMETRY.value in all_tags:
        if dq.empty:
            missing.append("sensor_faults: no DQ events generated")

    if EdgeCaseTag.MISSION_CONFLICT.value in all_tags:
        if not missions.empty:
            if "is_conflict" in missions.columns and not missions["is_conflict"].any():
                missing.append("mission_conflict: no conflict missions found")

    if EdgeCaseTag.OVERDUE_MAINTENANCE.value in all_tags:
        if maint.empty:
            missing.append("overdue_maintenance: no maintenance events")

    warnings = []
    if EdgeCaseTag.INSUFFICIENT_DATA.value in all_tags:
        if not tel.empty:
            counts = tel.groupby("asset_id").size()
            if not (counts < 10).any():
                warnings.append("insufficient_data asset may have more rows than expected")

    if missing:
        return CheckResult(
            name="edge_cases",
            passed=False,
            details=f"Missing evidence: {missing}",
            warnings=warnings,
        )
    return CheckResult(
        name="edge_cases",
        passed=True,
        details=f"{len(all_tags)} edge case types injected and detected",
        warnings=warnings,
    )


def _check_label_correctness(result: SimulationResult) -> CheckResult:
    """Verify failure event timestamps match truth health trajectories."""
    failures = result.truth.get("failure_events", pd.DataFrame())
    health = result.truth.get("component_health_trajectories", pd.DataFrame())

    if failures.empty:
        return CheckResult(
            name="label_correctness",
            passed=True,
            details="No failures to validate",
        )

    violations = 0
    for _, row in failures.iterrows():
        cid = row["component_id"]
        ft = row["occurred_at"]
        traj = health[health["component_id"] == cid]
        if traj.empty:
            violations += 1
            continue
        # Health at failure timestamp should be near zero
        traj_ts = pd.to_datetime(traj["timestamp"])
        closest_idx = (traj_ts - pd.Timestamp(ft)).abs().idxmin()
        health_at_failure = traj.loc[closest_idx, "true_health"]
        if health_at_failure > 0.15:
            violations += 1

    if violations > 0:
        return CheckResult(
            name="label_correctness",
            passed=False,
            details=f"{violations}/{len(failures)} failure events have health > 0.15 at failure time",
        )
    return CheckResult(
        name="label_correctness",
        passed=True,
        details=f"{len(failures)} failure events match truth trajectories",
    )


def _check_censored_no_failure(result: SimulationResult) -> CheckResult:
    """Verify censored assets (no failure event) have no failure_events record."""
    failures = result.truth.get("failure_events", pd.DataFrame())
    assets = result.observable.get("assets", pd.DataFrame())
    health = result.truth.get("component_health_trajectories", pd.DataFrame())

    if assets.empty or health.empty:
        return CheckResult(name="censored_no_failure", passed=True, details="No data")

    # Assets with active status should have no failure event
    active_assets = set(assets[assets["is_active"] == True]["asset_id"].tolist())  # noqa: E712
    if not failures.empty:
        failed_asset_ids = set(failures["asset_id"].tolist())
        overlap = active_assets & failed_asset_ids
        if overlap:
            return CheckResult(
                name="censored_no_failure",
                passed=False,
                details=f"{len(overlap)} active assets have failure events",
            )

    return CheckResult(
        name="censored_no_failure",
        passed=True,
        details="All active assets are free of failure events",
    )
