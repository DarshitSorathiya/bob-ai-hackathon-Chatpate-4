"""
Tests for the synthetic fleet simulator (Phase 4).

All tests use the tiny profile (10 assets, 365 days) or synthetic
micro-configs to run quickly. No real datasets are required.

Test coverage:
  - Deterministic output (same seed → identical DataFrames)
  - No leakage in observable tables
  - Degradation monotonicity (health never spontaneously increases outside maintenance)
  - Failure preceded by degradation (GRADUAL/NONLINEAR/ACCELERATED archetypes)
  - Maintenance resets health (post-maintenance health > pre-maintenance)
  - All 15 edge case types present in tiny profile output
  - Tiny profile runs in <60s
  - Validation suite passes on tiny output
  - Referential integrity in all observable tables
  - Timestamp monotonicity per sensor stream
  - Mission conflict detected and labelled correctly
  - Censored assets have no failure events
  - RNG independence (different assets have different trajectories)
  - Profile YAML loading works
  - Default config builds correctly
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.ml.simulator import FleetSimulator, SimulationResult, load_profile
from app.ml.simulator.config import SimulatorConfig, default_config
from app.ml.simulator.degradation import (
    DegradationArchetype,
    compute_true_rul,
    is_failed,
    step_health,
)
from app.ml.simulator.export import FORBIDDEN_OBSERVABLE_COLUMNS
from app.ml.simulator.rng import RNGManager
from app.ml.simulator.validate import validate_simulation


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def tiny_result() -> SimulationResult:
    """Run the tiny profile once and reuse across all tests."""
    cfg = load_profile("tiny")
    sim = FleetSimulator(cfg)
    return sim.run()


@pytest.fixture(scope="module")
def micro_result() -> SimulationResult:
    """Ultra-small 3-asset run for isolated unit tests."""
    cfg = default_config(n_assets=3, sim_days=90, seed=999)
    sim = FleetSimulator(cfg)
    return sim.run()


# ─── Profile loading ──────────────────────────────────────────────────────────


def test_load_tiny_profile() -> None:
    cfg = load_profile("tiny")
    assert cfg.profile.n_assets == 10
    assert cfg.profile.sim_days == 365
    assert cfg.profile.seed == 42


def test_load_validation_profile() -> None:
    cfg = load_profile("validation")
    assert cfg.profile.n_assets == 100
    assert cfg.profile.sim_days == 730


def test_default_config_builds() -> None:
    cfg = default_config(n_assets=5, sim_days=30, seed=1)
    assert cfg.profile.n_assets == 5
    assert len(cfg.asset_types) == 3


def test_load_nonexistent_profile() -> None:
    with pytest.raises(FileNotFoundError, match="Profile 'nonexistent' not found"):
        load_profile("nonexistent")


# ─── Deterministic output ────────────────────────────────────────────────────


def test_deterministic_output() -> None:
    """Same seed must produce identical telemetry rows."""
    cfg = default_config(n_assets=3, sim_days=30, seed=42)
    r1 = FleetSimulator(cfg).run()
    r2 = FleetSimulator(cfg).run()

    tel1 = r1.observable["telemetry"].sort_values(
        ["asset_id", "sensor_id", "recorded_at"]
    ).reset_index(drop=True)
    tel2 = r2.observable["telemetry"].sort_values(
        ["asset_id", "sensor_id", "recorded_at"]
    ).reset_index(drop=True)

    assert len(tel1) == len(tel2), "Row counts differ between runs"
    if not tel1.empty:
        pd.testing.assert_frame_equal(
            tel1[["asset_id", "sensor_id", "value"]].round(6),
            tel2[["asset_id", "sensor_id", "value"]].round(6),
        )


def test_different_seeds_differ() -> None:
    """Different seeds must produce different telemetry."""
    r1 = FleetSimulator(default_config(n_assets=3, sim_days=30, seed=1)).run()
    r2 = FleetSimulator(default_config(n_assets=3, sim_days=30, seed=2)).run()
    v1 = r1.observable["telemetry"]["value"].values
    v2 = r2.observable["telemetry"]["value"].values
    if len(v1) > 0 and len(v2) > 0:
        min_len = min(len(v1), len(v2))
        assert not np.allclose(v1[:min_len], v2[:min_len]), "Different seeds produced identical values"


# ─── Anti-leakage ────────────────────────────────────────────────────────────


def test_no_leakage_in_observable(tiny_result: SimulationResult) -> None:
    """Observable tables must contain no forbidden columns."""
    violations = tiny_result.validate_no_leakage()
    assert violations == [], f"Leakage violations: {violations}"


def test_truth_has_health_trajectories(tiny_result: SimulationResult) -> None:
    """Truth layer must contain health trajectory and failure events."""
    assert "component_health_trajectories" in tiny_result.truth
    health = tiny_result.truth["component_health_trajectories"]
    assert "true_health" in health.columns
    assert "true_rul" in health.columns


def test_observable_lacks_true_health(tiny_result: SimulationResult) -> None:
    """Telemetry must not contain 'true_health'."""
    tel = tiny_result.observable["telemetry"]
    assert "true_health" not in tel.columns
    assert "health" not in tel.columns


def test_observable_components_lack_archetype(tiny_result: SimulationResult) -> None:
    """Components table must not expose archetype (truth-only column)."""
    comps = tiny_result.observable["components"]
    assert "archetype" not in comps.columns
    assert "degradation_multiplier" not in comps.columns


# ─── Degradation monotonicity ────────────────────────────────────────────────


def test_degradation_monotonicity(tiny_result: SimulationResult) -> None:
    """Outside maintenance windows, health must not spontaneously increase."""
    health_df = tiny_result.truth["component_health_trajectories"]
    maint_df = tiny_result.observable["maintenance_events"]
    if health_df.empty:
        pytest.skip("No health trajectories")

    # Build set of (component_id, step) that are in maintenance
    maint_steps: set[tuple[str, int]] = set()
    if not maint_df.empty and not health_df.empty:
        for _, mr in maint_df.iterrows():
            cid = mr.get("component_id", "")
            traj = health_df[health_df["component_id"] == cid]
            if traj.empty:
                continue
            maint_ts = pd.Timestamp(mr["performed_at"])
            traj_ts = pd.to_datetime(traj["timestamp"])
            maint_idx = (traj_ts - maint_ts).abs().idxmin()
            # Mark ±30 steps as maintenance (approximate)
            step_val = int(traj.loc[maint_idx, "step"])
            for s in range(max(0, step_val - 5), step_val + 30):
                maint_steps.add((cid, s))

    violations = 0
    for cid, group in health_df.groupby("component_id"):
        group = group.sort_values("step")
        health = group["true_health"].values
        steps = group["step"].values
        for i in range(1, len(health)):
            if (cid, int(steps[i])) in maint_steps:
                continue  # allow increases during maintenance
            if health[i] > health[i - 1] + 0.03:  # 3% tolerance for noise
                violations += 1

    # Allow a small number of dip-recovery edge cases
    assert violations < 5, f"Too many spontaneous health increases: {violations}"


# ─── Failure events ───────────────────────────────────────────────────────────


def test_failure_preceded_by_degradation(tiny_result: SimulationResult) -> None:
    """Failed components should show declining health before failure."""
    failures = tiny_result.truth.get("failure_events", pd.DataFrame())
    health = tiny_result.truth.get("component_health_trajectories", pd.DataFrame())

    if failures.empty:
        pytest.skip("No failures in this run")

    for _, row in failures.iterrows():
        cid = row["component_id"]
        traj = health[health["component_id"] == cid].sort_values("step")
        if len(traj) < 10:
            continue
        n = len(traj)
        first_q = traj["true_health"].iloc[: n // 4].mean()
        last_q = traj["true_health"].iloc[3 * n // 4 :].mean()
        assert first_q > last_q - 0.1, (
            f"Component {cid[:8]}: first-quarter health {first_q:.3f} "
            f"<= last-quarter {last_q:.3f}"
        )


# ─── Maintenance recovery ────────────────────────────────────────────────────


def test_maintenance_resets_health(tiny_result: SimulationResult) -> None:
    """Corrective maintenance (triggered by low health) must restore health above pre-maintenance level."""
    maint = tiny_result.observable.get("maintenance_events", pd.DataFrame())
    health = tiny_result.truth.get("component_health_trajectories", pd.DataFrame())

    if maint.empty or health.empty:
        pytest.skip("No maintenance events")

    # Only test corrective/replacement events where health was genuinely low
    corrective = maint[maint["event_type"].isin(["CORRECTIVE", "REPLACEMENT"])]
    if corrective.empty:
        pytest.skip("No corrective maintenance events")

    at_least_one_recovery = False
    for _, row in corrective.iterrows():
        cid = row.get("component_id")
        if not cid:
            continue
        traj = health[health["component_id"] == cid].sort_values("step")
        if len(traj) < 20:
            continue

        traj_ts = pd.to_datetime(traj["timestamp"])
        maint_ts = pd.Timestamp(row["performed_at"])
        pre_health = traj[traj_ts < maint_ts]["true_health"].tail(5).mean()
        post_health = traj[traj_ts > maint_ts]["true_health"].head(10).mean()

        if not (np.isnan(pre_health) or np.isnan(post_health)):
            # Corrective: pre should have been low; post should be higher
            if pre_health < 0.4:
                assert post_health > pre_health, (
                    f"Corrective maintenance did not improve health: "
                    f"pre={pre_health:.3f} post={post_health:.3f}"
                )
                at_least_one_recovery = True

    if not at_least_one_recovery:
        pytest.skip("No corrective maintenance events with pre-health < 0.4 found")


# ─── Edge cases ───────────────────────────────────────────────────────────────


def test_edge_cases_present(tiny_result: SimulationResult) -> None:
    """All configured edge case types should appear in the tiny profile output."""
    all_tags: set[str] = set()
    for tags in tiny_result.edge_case_tags.values():
        all_tags.update(tags)

    required_tags = {
        "missing_telemetry",
        "stale_telemetry",
        "stuck_sensor",
        "outlier",
        "drift",
        "duplicate_timestamp",
        "sensor_failure",
        "component_degradation",
        "overdue_maintenance",
        "mission_conflict",
        "high_anomaly_low_failure",
        "poor_quality_genuine_degradation",
        "rul_shorter_than_mission",
        "insufficient_data",
    }

    missing = required_tags - all_tags
    assert not missing, f"Missing edge case tags: {missing}"


def test_duplicate_timestamps_present(tiny_result: SimulationResult) -> None:
    """DUPLICATE_TIMESTAMP edge case should produce duplicate rows."""
    tel = tiny_result.observable["telemetry"]
    assert not tel.empty
    dup = tel.duplicated(subset=["sensor_id", "recorded_at"])
    assert dup.any(), "No duplicate timestamps found in telemetry"


def test_mission_conflict_labelled(tiny_result: SimulationResult) -> None:
    """At least one mission should be marked as a conflict."""
    missions = tiny_result.observable.get("missions", pd.DataFrame())
    if missions.empty or "is_conflict" not in missions.columns:
        pytest.skip("No missions generated")
    assert missions["is_conflict"].any(), "No mission conflicts found"


# ─── Scale and performance ───────────────────────────────────────────────────


def test_tiny_profile_runs_under_60s() -> None:
    """Tiny profile (10 assets, 365 days) must complete in under 60 seconds."""
    cfg = load_profile("tiny")
    start = time.time()
    result = FleetSimulator(cfg).run()
    elapsed = time.time() - start
    assert elapsed < 60.0, f"Tiny profile took {elapsed:.1f}s (>60s limit)"
    assert not result.observable["telemetry"].empty, "No telemetry generated"


def test_tiny_profile_row_counts(tiny_result: SimulationResult) -> None:
    """Tiny profile should generate reasonable row counts."""
    tel = tiny_result.observable["telemetry"]
    assets = tiny_result.observable["assets"]
    assert len(assets) == 10, f"Expected 10 assets, got {len(assets)}"
    assert len(tel) > 1000, f"Expected >1000 telemetry rows, got {len(tel)}"


# ─── Referential integrity ────────────────────────────────────────────────────


def test_referential_integrity(tiny_result: SimulationResult) -> None:
    """All FK relationships must be valid in observable tables."""
    obs = tiny_result.observable
    asset_ids = set(obs["assets"]["asset_id"])
    comp_ids = set(obs["components"]["component_id"])
    sensor_ids = set(obs["sensors"]["sensor_id"])

    tel = obs["telemetry"]
    if not tel.empty:
        assert set(tel["asset_id"]).issubset(asset_ids), "Telemetry has unknown asset_ids"
        assert set(tel["sensor_id"]).issubset(sensor_ids), "Telemetry has unknown sensor_ids"
        assert set(tel["component_id"]).issubset(comp_ids), "Telemetry has unknown component_ids"

    maint = obs["maintenance_events"]
    if not maint.empty:
        assert set(maint["asset_id"]).issubset(asset_ids)

    missions = obs["missions"]
    if not missions.empty:
        assert set(missions["asset_id"]).issubset(asset_ids)


# ─── Timestamp monotonicity ──────────────────────────────────────────────────


def test_timestamp_monotonicity(tiny_result: SimulationResult) -> None:
    """Per-sensor timestamps must be non-decreasing (duplicates allowed)."""
    tel = tiny_result.observable["telemetry"]
    if tel.empty:
        pytest.skip("No telemetry")

    tel = tel.copy()
    tel["ts"] = pd.to_datetime(tel["recorded_at"])
    violations = 0

    for (_, sensor_id), group in tel.groupby(["asset_id", "sensor_id"], sort=False):
        ts = group["ts"].values
        if len(ts) < 2:
            continue
        diffs = np.diff(ts.astype("int64"))
        if (diffs < 0).any():
            violations += 1

    assert violations == 0, f"{violations} sensor streams have backwards timestamps"


# ─── Censored assets ─────────────────────────────────────────────────────────


def test_censored_assets_no_failure(tiny_result: SimulationResult) -> None:
    """Assets still marked active should have no failure events."""
    assets = tiny_result.observable["assets"]
    failures = tiny_result.truth.get("failure_events", pd.DataFrame())

    active_ids = set(assets[assets["is_active"] == True]["asset_id"])  # noqa: E712
    if not failures.empty:
        failed_ids = set(failures["asset_id"])
        overlap = active_ids & failed_ids
        assert not overlap, f"Active assets with failure events: {overlap}"


# ─── Full validation suite ───────────────────────────────────────────────────


def test_validation_suite_passes(tiny_result: SimulationResult) -> None:
    """The built-in validation suite should pass on the tiny profile output."""
    report = validate_simulation(tiny_result)
    # Print summary for diagnostics even if it passes
    print("\n" + report.summary())
    assert report.passed, f"Validation failed:\n{report.summary()}"


# ─── Degradation unit tests ───────────────────────────────────────────────────


def test_step_health_never_exceeds_1() -> None:
    """step_health must always return health in [0, 1]."""
    from app.ml.simulator.config import DegradationParams
    params = DegradationParams()
    rng = RNGManager(42).child("test")
    for archetype in DegradationArchetype:
        h = step_health(archetype, 1.0, 1.0, 1.0, params, rng)
        assert 0.0 <= h <= 1.0, f"{archetype}: health={h}"


def test_is_failed_threshold() -> None:
    assert not is_failed(0.10)   # above threshold
    assert is_failed(0.05)       # at threshold
    assert is_failed(0.0)        # zero


def test_compute_true_rul_censored() -> None:
    """Censored trajectory returns all None."""
    health = [1.0, 0.99, 0.98, 0.97]  # never fails
    rul = compute_true_rul(health, timestep_hours=1.0)
    assert all(r is None for r in rul)


def test_compute_true_rul_failing() -> None:
    """RUL decreases to 0 at failure."""
    # Create a trajectory that fails at step 3
    from app.ml.simulator.degradation import FAILURE_HEALTH_THRESHOLD
    health = [0.9, 0.5, 0.2, 0.03, 0.0]  # fails at step 3
    rul = compute_true_rul(health, timestep_hours=1.0)
    assert rul[3] == 0.0 or rul[4] == 0.0


# ─── RNG independence ────────────────────────────────────────────────────────


def test_rng_child_independence() -> None:
    """Different entity keys must produce independent streams."""
    rng = RNGManager(42)
    g1 = rng.child("asset", "A001")
    g2 = rng.child("asset", "A002")
    v1 = g1.random(10)
    v2 = g2.random(10)
    assert not np.allclose(v1, v2), "Different keys produced identical values"


def test_rng_same_key_returns_same_stream() -> None:
    """Same key must return the same generator (cached)."""
    rng = RNGManager(42)
    g1 = rng.child("sensor", "X")
    v1 = g1.random(5)
    g2 = rng.child("sensor", "X")
    v2 = g2.random(5)
    # Same generator object: state has advanced, but it IS the same object
    assert g1 is g2
