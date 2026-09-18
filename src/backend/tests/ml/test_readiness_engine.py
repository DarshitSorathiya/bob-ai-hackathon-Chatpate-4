"""
Comprehensive tests for the Explainable Readiness Engine (Phase 7).

Coverage strategy:
  - One test per named rule (R1–R12 + READY path)
  - Priority/precedence tests (higher-priority rule wins when multiple fire)
  - Contradictory-condition tests (e.g. READY prediction + stale data)
  - Edge cases: boundary values, None inputs, zero mission duration
  - Determinism: same input always produces same output
  - UNKNOWN != READY enforcement
  - Confidence score behaviour
  - All 14 edge cases from spec §18 (ARCHITECTURE.md)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ml.readiness import (
    ComponentState,
    ContributingFactor,
    MaintenanceStatus,
    ReadinessEngine,
    ReadinessInput,
    ReadinessOutput,
    ReadinessStatus,
    ReadinessThresholds,
    ReasonCode,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _base_input(**overrides) -> ReadinessInput:
    """Return a fully populated READY-baseline input.

    All optional ML fields are set to clearly healthy values.
    Override individual fields to trigger specific rules.
    """
    defaults = dict(
        asset_id="asset-001",
        asset_code="AH-64-01",
        evaluated_at=NOW,
        maintenance_status=MaintenanceStatus.OPERATIONAL,
        has_blocking_work_order=False,
        blocking_work_order_ids=[],
        hours_since_last_maintenance=48.0,
        maintenance_overdue_hours=0.0,
        maintenance_is_critical=False,
        component_states={"ENGINE_CORE": ComponentState.NOMINAL},
        critical_components={"ENGINE_CORE"},
        rul_hours=500.0,
        rul_lower=450.0,
        rul_upper=550.0,
        failure_probability=0.05,
        anomaly_score=0.20,
        prediction_confidence=0.90,
        observation_count=200,
        hours_since_last_reading=1.0,
        stale_sensor_codes=[],
        fault_sensor_codes=[],
        drifting_sensor_codes=[],
        mission_duration_hours=4.0,
        mission_id="MISSION-001",
    )
    defaults.update(overrides)
    return ReadinessInput(**defaults)


@pytest.fixture
def engine() -> ReadinessEngine:
    return ReadinessEngine()


def _reason_codes(output: ReadinessOutput) -> list[ReasonCode]:
    return [f.code for f in output.contributing_factors]


# ===========================================================================
# Section 1: READY baseline
# ===========================================================================

class TestReadyBaseline:
    def test_healthy_asset_is_ready(self, engine):
        out = engine.evaluate(_base_input())
        assert out.status == ReadinessStatus.READY

    def test_primary_reason_is_all_checks_passed(self, engine):
        out = engine.evaluate(_base_input())
        assert out.primary_reason == ReasonCode.ALL_CHECKS_PASSED

    def test_confidence_near_1_for_healthy_asset(self, engine):
        out = engine.evaluate(_base_input())
        assert out.confidence >= 0.95

    def test_output_has_one_factor_for_ready(self, engine):
        out = engine.evaluate(_base_input())
        assert len(out.contributing_factors) == 1
        assert out.contributing_factors[0].code == ReasonCode.ALL_CHECKS_PASSED

    def test_output_preserves_asset_ids(self, engine):
        out = engine.evaluate(_base_input(asset_id="x-123", asset_code="HAWK-99"))
        assert out.asset_id == "x-123"
        assert out.asset_code == "HAWK-99"

    def test_output_preserves_mission_id(self, engine):
        out = engine.evaluate(_base_input(mission_id="M-555"))
        assert out.mission_id == "M-555"

    def test_output_preserves_evaluated_at(self, engine):
        out = engine.evaluate(_base_input())
        assert out.evaluated_at == NOW

    def test_thresholds_snapshot_attached(self, engine):
        t = ReadinessThresholds(not_ready_failure_prob=0.30)
        eng = ReadinessEngine(thresholds=t)
        out = eng.evaluate(_base_input())
        assert out.thresholds_used.not_ready_failure_prob == 0.30


# ===========================================================================
# Section 2: NOT_READY — individual rule tests
# ===========================================================================

class TestNotReadyRules:
    # --- R1: Blocking work order -------------------------------------------
    def test_r1_blocking_work_order(self, engine):
        out = engine.evaluate(_base_input(
            has_blocking_work_order=True,
            blocking_work_order_ids=["WO-001", "WO-002"],
        ))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.CRITICAL_MAINTENANCE_OPEN

    def test_r1_factor_contains_work_order_ids(self, engine):
        out = engine.evaluate(_base_input(
            has_blocking_work_order=True,
            blocking_work_order_ids=["WO-777"],
        ))
        factor = next(f for f in out.contributing_factors
                      if f.code == ReasonCode.CRITICAL_MAINTENANCE_OPEN)
        assert "WO-777" in factor.evidence["blocking_work_order_ids"]

    def test_r1_empty_blocking_list_still_not_ready(self, engine):
        """has_blocking_work_order=True but empty ID list — flag still triggers."""
        out = engine.evaluate(_base_input(
            has_blocking_work_order=True,
            blocking_work_order_ids=[],
        ))
        assert out.status == ReadinessStatus.NOT_READY

    # --- R2: Under maintenance ---------------------------------------------
    def test_r2_under_maintenance(self, engine):
        out = engine.evaluate(_base_input(
            maintenance_status=MaintenanceStatus.UNDER_MAINTENANCE,
        ))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.ASSET_UNDER_MAINTENANCE

    def test_r2_scheduled_maintenance_does_not_block(self, engine):
        """SCHEDULED_MAINTENANCE means pre-positioned, not currently offline."""
        out = engine.evaluate(_base_input(
            maintenance_status=MaintenanceStatus.SCHEDULED_MAINTENANCE,
        ))
        # Scheduled is not the same as UNDER_MAINTENANCE
        assert ReasonCode.ASSET_UNDER_MAINTENANCE not in _reason_codes(out)

    def test_r2_returned_to_service_is_operational(self, engine):
        out = engine.evaluate(_base_input(
            maintenance_status=MaintenanceStatus.RETURNED_TO_SERVICE,
        ))
        assert ReasonCode.ASSET_UNDER_MAINTENANCE not in _reason_codes(out)

    # --- R3: Critical component failure ------------------------------------
    def test_r3_critical_component_failed(self, engine):
        out = engine.evaluate(_base_input(
            component_states={"ENGINE_CORE": ComponentState.FAILED},
            critical_components={"ENGINE_CORE"},
        ))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.CRITICAL_COMPONENT_FAILURE

    def test_r3_non_critical_component_failed_does_not_block(self, engine):
        """A non-critical component failure should NOT trigger NOT_READY via R3."""
        out = engine.evaluate(_base_input(
            component_states={
                "ENGINE_CORE": ComponentState.NOMINAL,
                "CABIN_LIGHT": ComponentState.FAILED,
            },
            critical_components={"ENGINE_CORE"},
        ))
        assert ReasonCode.CRITICAL_COMPONENT_FAILURE not in _reason_codes(out)

    def test_r3_multiple_critical_components_all_in_evidence(self, engine):
        out = engine.evaluate(_base_input(
            component_states={
                "ENGINE_CORE": ComponentState.FAILED,
                "ROTOR_MAIN": ComponentState.FAILED,
            },
            critical_components={"ENGINE_CORE", "ROTOR_MAIN"},
        ))
        factor = next(f for f in out.contributing_factors
                      if f.code == ReasonCode.CRITICAL_COMPONENT_FAILURE)
        assert "ENGINE_CORE" in factor.evidence["failed_components"]
        assert "ROTOR_MAIN" in factor.evidence["failed_components"]

    def test_r3_degraded_critical_component_does_not_trigger_r3(self, engine):
        """DEGRADED is not FAILED — R3 should not fire; AT_RISK may fire via other rules."""
        out = engine.evaluate(_base_input(
            component_states={"ENGINE_CORE": ComponentState.DEGRADED},
            critical_components={"ENGINE_CORE"},
        ))
        assert ReasonCode.CRITICAL_COMPONENT_FAILURE not in _reason_codes(out)

    # --- R4a: Sensor fault -------------------------------------------------
    def test_r4a_sensor_fault_not_ready(self, engine):
        out = engine.evaluate(_base_input(fault_sensor_codes=["TEMP-01"]))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.SENSOR_FAULT_DETECTED

    def test_r4a_multiple_fault_sensors_in_evidence(self, engine):
        out = engine.evaluate(_base_input(
            fault_sensor_codes=["TEMP-01", "VIB-03"],
        ))
        factor = next(f for f in out.contributing_factors
                      if f.code == ReasonCode.SENSOR_FAULT_DETECTED)
        assert sorted(factor.evidence["fault_sensors"]) == ["TEMP-01", "VIB-03"]

    # --- R4b: Overdue critical maintenance ---------------------------------
    def test_r4b_critical_maintenance_overdue_beyond_threshold(self, engine):
        out = engine.evaluate(_base_input(
            maintenance_is_critical=True,
            maintenance_overdue_hours=72.0,  # > default 48 h
        ))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.OVERDUE_CRITICAL_MAINTENANCE

    def test_r4b_exactly_at_threshold_not_triggered(self, engine):
        """Exactly at the threshold: rule uses strict >, so threshold itself is OK."""
        out = engine.evaluate(_base_input(
            maintenance_is_critical=True,
            maintenance_overdue_hours=48.0,  # == threshold, not >
        ))
        assert ReasonCode.OVERDUE_CRITICAL_MAINTENANCE not in _reason_codes(out)

    def test_r4b_critical_but_not_overdue_ok(self, engine):
        out = engine.evaluate(_base_input(
            maintenance_is_critical=True,
            maintenance_overdue_hours=0.0,
        ))
        assert ReasonCode.OVERDUE_CRITICAL_MAINTENANCE not in _reason_codes(out)

    def test_r4b_non_critical_overdue_does_not_trigger_r4b(self, engine):
        """Non-critical overdue maintenance triggers AT_RISK (R12), not NOT_READY."""
        out = engine.evaluate(_base_input(
            maintenance_is_critical=False,
            maintenance_overdue_hours=100.0,
        ))
        assert ReasonCode.OVERDUE_CRITICAL_MAINTENANCE not in _reason_codes(out)

    # --- R5: High failure probability --------------------------------------
    def test_r5_failure_prob_above_not_ready_threshold(self, engine):
        out = engine.evaluate(_base_input(failure_probability=0.50))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.HIGH_FAILURE_PROBABILITY

    def test_r5_exactly_at_threshold_not_triggered(self, engine):
        """0.45 == threshold; strict > means it does not trigger."""
        out = engine.evaluate(_base_input(failure_probability=0.45))
        assert ReasonCode.HIGH_FAILURE_PROBABILITY not in _reason_codes(out)

    def test_r5_failure_prob_none_does_not_crash(self, engine):
        """Missing failure_probability should not crash the engine."""
        out = engine.evaluate(_base_input(failure_probability=None))
        assert out.status in ReadinessStatus

    # --- R6: RUL below mission requirement ---------------------------------
    def test_r6_rul_below_safety_margin(self, engine):
        # mission=8 h, margin=1.25 → need RUL > 10 h
        out = engine.evaluate(_base_input(mission_duration_hours=8.0, rul_hours=9.0))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.RUL_BELOW_MISSION_REQUIREMENT

    def test_r6_rul_exactly_at_safety_margin_not_triggered(self, engine):
        # mission=8 h, margin=1.25 → boundary = 10.0
        out = engine.evaluate(_base_input(mission_duration_hours=8.0, rul_hours=10.0))
        assert ReasonCode.RUL_BELOW_MISSION_REQUIREMENT not in _reason_codes(out)

    def test_r6_zero_mission_duration_does_not_trigger_r6(self, engine):
        """If no mission duration is specified, R6 must not fire."""
        out = engine.evaluate(_base_input(mission_duration_hours=0.0, rul_hours=1.0))
        assert ReasonCode.RUL_BELOW_MISSION_REQUIREMENT not in _reason_codes(out)

    def test_r6_rul_none_does_not_trigger_r6(self, engine):
        """Missing RUL → no RUL-based not_ready; UNKNOWN via R7a."""
        out = engine.evaluate(_base_input(
            rul_hours=None,
            failure_probability=None,
            anomaly_score=None,
        ))
        assert ReasonCode.RUL_BELOW_MISSION_REQUIREMENT not in _reason_codes(out)


# ===========================================================================
# Section 3: UNKNOWN — individual rule tests
# ===========================================================================

class TestUnknownRules:
    # --- R7a: No prediction -----------------------------------------------
    def test_r7a_no_prediction_returns_unknown(self, engine):
        out = engine.evaluate(_base_input(
            failure_probability=None,
            rul_hours=None,
            anomaly_score=None,
        ))
        assert out.status == ReadinessStatus.UNKNOWN
        assert out.primary_reason == ReasonCode.NO_PREDICTION_AVAILABLE

    def test_r7a_partial_prediction_is_unknown_for_operational_safety(self, engine):
        """Readiness fails closed unless both RUL and failure risk are present."""
        out = engine.evaluate(_base_input(
            failure_probability=0.05,
            rul_hours=None,
            anomaly_score=None,
        ))
        assert out.status == ReadinessStatus.UNKNOWN
        assert ReasonCode.NO_PREDICTION_AVAILABLE in _reason_codes(out)

    # --- R7b: Insufficient observations ------------------------------------
    def test_r7b_few_observations_returns_unknown(self, engine):
        out = engine.evaluate(_base_input(observation_count=3))
        assert out.status == ReadinessStatus.UNKNOWN
        assert ReasonCode.INSUFFICIENT_DATA in _reason_codes(out)

    def test_r7b_exactly_at_min_does_not_trigger(self, engine):
        out = engine.evaluate(_base_input(observation_count=10))
        assert ReasonCode.INSUFFICIENT_DATA not in _reason_codes(out)

    def test_r7b_zero_observations_returns_unknown(self, engine):
        out = engine.evaluate(_base_input(observation_count=0))
        assert ReasonCode.INSUFFICIENT_DATA in _reason_codes(out)

    def test_r7b_observation_count_none_does_not_trigger(self, engine):
        """None means unknown; do not raise INSUFFICIENT_DATA."""
        out = engine.evaluate(_base_input(observation_count=None))
        assert ReasonCode.INSUFFICIENT_DATA not in _reason_codes(out)

    # --- R7c: Low model confidence -----------------------------------------
    def test_r7c_low_confidence_returns_unknown(self, engine):
        out = engine.evaluate(_base_input(prediction_confidence=0.30))
        assert out.status == ReadinessStatus.UNKNOWN
        assert ReasonCode.LOW_PREDICTION_CONFIDENCE in _reason_codes(out)

    def test_r7c_exactly_at_min_confidence_not_triggered(self, engine):
        out = engine.evaluate(_base_input(prediction_confidence=0.50))
        assert ReasonCode.LOW_PREDICTION_CONFIDENCE not in _reason_codes(out)

    def test_r7c_confidence_none_does_not_crash(self, engine):
        out = engine.evaluate(_base_input(prediction_confidence=None))
        assert ReasonCode.LOW_PREDICTION_CONFIDENCE not in _reason_codes(out)

    # --- R7d: Stale critical telemetry ------------------------------------
    def test_r7d_stale_hours_returns_unknown(self, engine):
        out = engine.evaluate(_base_input(hours_since_last_reading=8.0))
        assert out.status == ReadinessStatus.UNKNOWN
        assert ReasonCode.STALE_CRITICAL_TELEMETRY in _reason_codes(out)

    def test_r7d_stale_sensor_codes_returns_unknown(self, engine):
        out = engine.evaluate(_base_input(
            hours_since_last_reading=1.0,  # overall ok
            stale_sensor_codes=["TEMP-01"],  # but this sensor is stale
        ))
        assert out.status == ReadinessStatus.UNKNOWN
        assert ReasonCode.STALE_CRITICAL_TELEMETRY in _reason_codes(out)

    def test_r7d_exactly_at_stale_threshold_not_triggered(self, engine):
        # threshold=4.0; exactly 4.0 is not > 4.0
        out = engine.evaluate(_base_input(hours_since_last_reading=4.0))
        assert ReasonCode.STALE_CRITICAL_TELEMETRY not in _reason_codes(out)

    def test_r7d_hours_none_and_no_stale_sensors_no_flag(self, engine):
        out = engine.evaluate(_base_input(
            hours_since_last_reading=None,
            stale_sensor_codes=[],
        ))
        assert ReasonCode.STALE_CRITICAL_TELEMETRY not in _reason_codes(out)

    # --- R7e: High failure prob + poor data quality -----------------------
    def test_r7e_high_fail_prob_with_low_confidence_unknown(self, engine):
        out = engine.evaluate(_base_input(
            failure_probability=0.25,   # > at_risk threshold (0.15)
            prediction_confidence=0.20, # < min_confidence (0.50)
        ))
        assert out.status == ReadinessStatus.UNKNOWN
        assert ReasonCode.PREDICTION_DATA_QUALITY_DEGRADED in _reason_codes(out)

    def test_r7e_high_fail_prob_with_good_confidence_not_triggered(self, engine):
        out = engine.evaluate(_base_input(
            failure_probability=0.25,
            prediction_confidence=0.80,
        ))
        assert ReasonCode.PREDICTION_DATA_QUALITY_DEGRADED not in _reason_codes(out)


# ===========================================================================
# Section 4: AT_RISK — individual rule tests
# ===========================================================================

class TestAtRiskRules:
    # --- R8: Elevated failure probability ----------------------------------
    def test_r8_elevated_failure_prob_at_risk(self, engine):
        out = engine.evaluate(_base_input(failure_probability=0.25))
        assert out.status == ReadinessStatus.AT_RISK
        assert out.primary_reason == ReasonCode.ELEVATED_FAILURE_PROBABILITY

    def test_r8_boundary_exactly_at_at_risk_threshold_not_triggered(self, engine):
        out = engine.evaluate(_base_input(failure_probability=0.15))
        assert ReasonCode.ELEVATED_FAILURE_PROBABILITY not in _reason_codes(out)

    def test_r8_above_not_ready_threshold_triggers_r5_not_r8(self, engine):
        """When failure_probability > not_ready threshold, R5 fires, not R8."""
        out = engine.evaluate(_base_input(failure_probability=0.50))
        assert out.status == ReadinessStatus.NOT_READY
        assert ReasonCode.HIGH_FAILURE_PROBABILITY in _reason_codes(out)
        assert ReasonCode.ELEVATED_FAILURE_PROBABILITY not in _reason_codes(out)

    # --- R9: RUL within AT_RISK margin ------------------------------------
    def test_r9_rul_within_at_risk_margin(self, engine):
        # mission=8 h; AT_RISK threshold = 8 * 2.0 = 16 h; NOT_READY = 8 * 1.25 = 10 h
        # RUL=12 h is between 10 and 16 → AT_RISK
        out = engine.evaluate(_base_input(mission_duration_hours=8.0, rul_hours=12.0))
        assert out.status == ReadinessStatus.AT_RISK
        assert ReasonCode.RUL_WITHIN_SAFETY_MARGIN in _reason_codes(out)

    def test_r9_rul_above_at_risk_margin_no_flag(self, engine):
        # mission=8 h; AT_RISK = 16 h; rul=20 > 16 → no AT_RISK flag
        out = engine.evaluate(_base_input(mission_duration_hours=8.0, rul_hours=20.0))
        assert ReasonCode.RUL_WITHIN_SAFETY_MARGIN not in _reason_codes(out)

    def test_r9_zero_mission_duration_does_not_trigger_r9(self, engine):
        out = engine.evaluate(_base_input(mission_duration_hours=0.0, rul_hours=5.0))
        assert ReasonCode.RUL_WITHIN_SAFETY_MARGIN not in _reason_codes(out)

    # --- R10: Anomaly detected --------------------------------------------
    def test_r10_high_anomaly_score_at_risk(self, engine):
        out = engine.evaluate(_base_input(anomaly_score=0.85))
        assert out.status == ReadinessStatus.AT_RISK
        assert out.primary_reason == ReasonCode.ANOMALY_DETECTED

    def test_r10_anomaly_below_threshold_not_triggered(self, engine):
        out = engine.evaluate(_base_input(anomaly_score=0.60))
        assert ReasonCode.ANOMALY_DETECTED not in _reason_codes(out)

    def test_r10_anomaly_none_not_triggered(self, engine):
        out = engine.evaluate(_base_input(anomaly_score=None))
        assert ReasonCode.ANOMALY_DETECTED not in _reason_codes(out)

    # --- R11: Sensor drift ------------------------------------------------
    def test_r11_drifting_sensors_at_risk(self, engine):
        out = engine.evaluate(_base_input(drifting_sensor_codes=["VIB-01"]))
        assert out.status == ReadinessStatus.AT_RISK
        assert ReasonCode.SENSOR_DRIFT in _reason_codes(out)

    def test_r11_no_drift_not_triggered(self, engine):
        out = engine.evaluate(_base_input(drifting_sensor_codes=[]))
        assert ReasonCode.SENSOR_DRIFT not in _reason_codes(out)

    # --- R12: Overdue routine maintenance ---------------------------------
    def test_r12_routine_overdue_at_risk(self, engine):
        out = engine.evaluate(_base_input(
            maintenance_is_critical=False,
            maintenance_overdue_hours=5.0,
        ))
        assert out.status == ReadinessStatus.AT_RISK
        assert ReasonCode.OVERDUE_ROUTINE_MAINTENANCE in _reason_codes(out)

    def test_r12_routine_not_overdue_not_triggered(self, engine):
        out = engine.evaluate(_base_input(
            maintenance_is_critical=False,
            maintenance_overdue_hours=0.0,
        ))
        assert ReasonCode.OVERDUE_ROUTINE_MAINTENANCE not in _reason_codes(out)


# ===========================================================================
# Section 5: Rule precedence / priority
# ===========================================================================

class TestRulePrecedence:
    def test_r1_overrides_r7a_unknown(self, engine):
        """Blocking work order should produce NOT_READY, not UNKNOWN."""
        out = engine.evaluate(_base_input(
            has_blocking_work_order=True,
            failure_probability=None,
            rul_hours=None,
            anomaly_score=None,
        ))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.CRITICAL_MAINTENANCE_OPEN

    def test_r1_overrides_r8_at_risk(self, engine):
        """Blocking work order is NOT_READY even if only AT_RISK metrics are present."""
        out = engine.evaluate(_base_input(
            has_blocking_work_order=True,
            failure_probability=0.25,  # AT_RISK level
        ))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.CRITICAL_MAINTENANCE_OPEN

    def test_r2_overrides_all_green_predictions(self, engine):
        """Asset under maintenance is NOT_READY even with perfect ML scores."""
        out = engine.evaluate(_base_input(
            maintenance_status=MaintenanceStatus.UNDER_MAINTENANCE,
            failure_probability=0.01,
            rul_hours=999.0,
        ))
        assert out.status == ReadinessStatus.NOT_READY

    def test_not_ready_overrides_unknown(self, engine):
        """When both NOT_READY and UNKNOWN factors exist, NOT_READY wins."""
        out = engine.evaluate(_base_input(
            has_blocking_work_order=True,
            observation_count=2,  # would cause UNKNOWN
        ))
        assert out.status == ReadinessStatus.NOT_READY

    def test_not_ready_overrides_at_risk(self, engine):
        """High failure probability (NOT_READY) overrides elevated anomaly (AT_RISK)."""
        out = engine.evaluate(_base_input(
            failure_probability=0.50,   # NOT_READY
            anomaly_score=0.90,         # AT_RISK
        ))
        assert out.status == ReadinessStatus.NOT_READY

    def test_unknown_overrides_at_risk(self, engine):
        """Stale telemetry (UNKNOWN) overrides elevated anomaly score (AT_RISK)."""
        out = engine.evaluate(_base_input(
            hours_since_last_reading=8.0,  # UNKNOWN
            anomaly_score=0.85,            # AT_RISK
        ))
        assert out.status == ReadinessStatus.UNKNOWN

    def test_multiple_not_ready_factors_all_collected(self, engine):
        """When multiple NOT_READY rules fire, ALL factors are collected."""
        out = engine.evaluate(_base_input(
            has_blocking_work_order=True,
            maintenance_status=MaintenanceStatus.UNDER_MAINTENANCE,
            failure_probability=0.50,
        ))
        assert out.status == ReadinessStatus.NOT_READY
        codes = _reason_codes(out)
        assert ReasonCode.CRITICAL_MAINTENANCE_OPEN in codes
        assert ReasonCode.ASSET_UNDER_MAINTENANCE in codes
        assert ReasonCode.HIGH_FAILURE_PROBABILITY in codes

    def test_primary_reason_is_first_not_ready_factor(self, engine):
        """The primary_reason must be the first NOT_READY rule that fired (R1)."""
        out = engine.evaluate(_base_input(
            has_blocking_work_order=True,
            failure_probability=0.50,
        ))
        assert out.primary_reason == ReasonCode.CRITICAL_MAINTENANCE_OPEN

    def test_at_risk_and_unknown_factors_shown_alongside_not_ready(self, engine):
        """All factors (not_ready + unknown + at_risk) are included in the output."""
        out = engine.evaluate(_base_input(
            has_blocking_work_order=True,
            hours_since_last_reading=8.0,   # UNKNOWN
            anomaly_score=0.85,             # AT_RISK
        ))
        codes = _reason_codes(out)
        assert ReasonCode.CRITICAL_MAINTENANCE_OPEN in codes
        assert ReasonCode.STALE_CRITICAL_TELEMETRY in codes
        assert ReasonCode.ANOMALY_DETECTED in codes


# ===========================================================================
# Section 6: Contradictory conditions
# ===========================================================================

class TestContradictoryConditions:
    def test_perfect_ml_scores_but_under_maintenance(self, engine):
        """Excellent ML predictions cannot override a maintenance lockout."""
        out = engine.evaluate(_base_input(
            maintenance_status=MaintenanceStatus.UNDER_MAINTENANCE,
            failure_probability=0.001,
            rul_hours=10000.0,
            anomaly_score=0.01,
            prediction_confidence=0.99,
        ))
        assert out.status == ReadinessStatus.NOT_READY

    def test_healthy_maintenance_but_stale_telemetry(self, engine):
        """No maintenance issues, but telemetry is stale → UNKNOWN, not READY."""
        out = engine.evaluate(_base_input(
            hours_since_last_reading=48.0,
            maintenance_status=MaintenanceStatus.OPERATIONAL,
        ))
        assert out.status == ReadinessStatus.UNKNOWN
        assert out.status != ReadinessStatus.READY

    def test_high_anomaly_but_low_failure_prob_is_at_risk_not_not_ready(self, engine):
        """High anomaly score + low failure probability → AT_RISK (investigate), not NOT_READY."""
        out = engine.evaluate(_base_input(
            anomaly_score=0.95,         # very high anomaly
            failure_probability=0.05,   # low failure probability
        ))
        assert out.status == ReadinessStatus.AT_RISK
        assert out.status != ReadinessStatus.NOT_READY

    def test_low_failure_prob_but_rul_just_above_cutoff_is_at_risk(self, engine):
        """RUL is in the AT_RISK band even when failure probability is low."""
        # mission=8 h; NOT_READY cutoff=10 h; AT_RISK cutoff=16 h; RUL=12 → AT_RISK
        out = engine.evaluate(_base_input(
            mission_duration_hours=8.0,
            rul_hours=12.0,
            failure_probability=0.03,  # very low
        ))
        assert out.status == ReadinessStatus.AT_RISK
        assert ReasonCode.RUL_WITHIN_SAFETY_MARGIN in _reason_codes(out)

    def test_unknown_from_missing_data_even_when_maintenance_ok(self, engine):
        """No prediction data → UNKNOWN even with perfect maintenance record."""
        out = engine.evaluate(_base_input(
            failure_probability=None,
            rul_hours=None,
            anomaly_score=None,
            maintenance_status=MaintenanceStatus.OPERATIONAL,
        ))
        assert out.status == ReadinessStatus.UNKNOWN

    def test_returned_to_service_can_be_ready(self, engine):
        """After maintenance completion, asset can re-attain READY."""
        out = engine.evaluate(_base_input(
            maintenance_status=MaintenanceStatus.RETURNED_TO_SERVICE,
        ))
        assert out.status == ReadinessStatus.READY

    def test_critical_component_fault_vs_component_failure(self, engine):
        """ComponentState.FAULT (sensor fault) should NOT trigger R3 (component failure)."""
        out = engine.evaluate(_base_input(
            component_states={"ENGINE_CORE": ComponentState.FAULT},
            critical_components={"ENGINE_CORE"},
        ))
        assert ReasonCode.CRITICAL_COMPONENT_FAILURE not in _reason_codes(out)

    def test_sensor_fault_and_component_failure_both_reported(self, engine):
        """Both sensor fault and component failure present — both reason codes appear."""
        out = engine.evaluate(_base_input(
            component_states={"ENGINE_CORE": ComponentState.FAILED},
            critical_components={"ENGINE_CORE"},
            fault_sensor_codes=["TEMP-SENSOR-01"],
        ))
        codes = _reason_codes(out)
        assert ReasonCode.CRITICAL_COMPONENT_FAILURE in codes
        assert ReasonCode.SENSOR_FAULT_DETECTED in codes
        assert out.status == ReadinessStatus.NOT_READY


# ===========================================================================
# Section 7: UNKNOWN != READY enforcement
# ===========================================================================

class TestUnknownNotReady:
    """UNKNOWN must never be treated as READY. These tests verify the engine
    never produces READY when evidence is missing or unreliable."""

    def test_no_predictions_returns_unknown_not_ready(self, engine):
        out = engine.evaluate(_base_input(
            failure_probability=None,
            rul_hours=None,
            anomaly_score=None,
        ))
        assert out.status == ReadinessStatus.UNKNOWN
        assert out.status != ReadinessStatus.READY

    def test_zero_observations_returns_unknown_not_ready(self, engine):
        out = engine.evaluate(_base_input(observation_count=0))
        assert out.status == ReadinessStatus.UNKNOWN
        assert out.status != ReadinessStatus.READY

    def test_stale_data_returns_unknown_not_ready(self, engine):
        out = engine.evaluate(_base_input(hours_since_last_reading=100.0))
        assert out.status == ReadinessStatus.UNKNOWN
        assert out.status != ReadinessStatus.READY

    def test_unknown_enum_value_not_equal_to_ready(self):
        assert ReadinessStatus.UNKNOWN != ReadinessStatus.READY
        assert ReadinessStatus.UNKNOWN.value == "UNKNOWN"


# ===========================================================================
# Section 8: Determinism
# ===========================================================================

class TestDeterminism:
    def test_same_input_same_output(self, engine):
        inp = _base_input(failure_probability=0.25, rul_hours=15.0)
        out1 = engine.evaluate(inp)
        out2 = engine.evaluate(inp)
        assert out1.status == out2.status
        assert out1.primary_reason == out2.primary_reason
        assert len(out1.contributing_factors) == len(out2.contributing_factors)
        assert out1.confidence == out2.confidence

    def test_determinism_for_not_ready(self, engine):
        inp = _base_input(has_blocking_work_order=True)
        results = [engine.evaluate(inp) for _ in range(5)]
        assert all(r.status == ReadinessStatus.NOT_READY for r in results)

    def test_determinism_for_unknown(self, engine):
        inp = _base_input(failure_probability=None, rul_hours=None, anomaly_score=None)
        results = [engine.evaluate(inp) for _ in range(5)]
        assert all(r.status == ReadinessStatus.UNKNOWN for r in results)

    def test_different_inputs_different_outputs(self, engine):
        ready_inp = _base_input()
        not_ready_inp = _base_input(has_blocking_work_order=True)
        assert engine.evaluate(ready_inp).status != engine.evaluate(not_ready_inp).status


# ===========================================================================
# Section 9: Custom thresholds
# ===========================================================================

class TestCustomThresholds:
    def test_stricter_failure_prob_threshold(self):
        """With a stricter threshold, a lower failure probability triggers NOT_READY."""
        strict = ReadinessEngine(thresholds=ReadinessThresholds(not_ready_failure_prob=0.20))
        out = strict.evaluate(_base_input(failure_probability=0.25))
        assert out.status == ReadinessStatus.NOT_READY

    def test_looser_failure_prob_threshold(self):
        """With a looser threshold, a moderately high failure probability is AT_RISK only."""
        loose = ReadinessEngine(thresholds=ReadinessThresholds(
            not_ready_failure_prob=0.60,
            at_risk_failure_prob=0.30,
        ))
        out = loose.evaluate(_base_input(failure_probability=0.45))
        assert out.status == ReadinessStatus.AT_RISK

    def test_custom_stale_threshold(self):
        """With a shorter stale threshold, data that was fine before becomes stale."""
        strict = ReadinessEngine(thresholds=ReadinessThresholds(stale_hours=0.5))
        out = strict.evaluate(_base_input(hours_since_last_reading=1.0))
        assert out.status == ReadinessStatus.UNKNOWN
        assert ReasonCode.STALE_CRITICAL_TELEMETRY in _reason_codes(out)

    def test_custom_rul_safety_margin(self):
        """With a larger safety margin, an asset that was READY becomes NOT_READY."""
        strict = ReadinessEngine(thresholds=ReadinessThresholds(not_ready_rul_margin=2.0))
        # mission=8 h, RUL=14 h; required = 8 * 2.0 = 16 h → RUL 14 < 16 → NOT_READY
        out = strict.evaluate(_base_input(mission_duration_hours=8.0, rul_hours=14.0))
        assert out.status == ReadinessStatus.NOT_READY

    def test_custom_critical_overdue_hours(self):
        """Custom overdue threshold triggers NOT_READY at a different value."""
        strict = ReadinessEngine(thresholds=ReadinessThresholds(critical_overdue_hours=12.0))
        out = strict.evaluate(_base_input(
            maintenance_is_critical=True,
            maintenance_overdue_hours=15.0,  # 15 > 12 → NOT_READY
        ))
        assert out.status == ReadinessStatus.NOT_READY

    def test_thresholds_are_snapshotted_in_output(self):
        t = ReadinessThresholds(not_ready_failure_prob=0.35, stale_hours=2.0)
        eng = ReadinessEngine(thresholds=t)
        out = eng.evaluate(_base_input())
        assert out.thresholds_used.not_ready_failure_prob == 0.35
        assert out.thresholds_used.stale_hours == 2.0


# ===========================================================================
# Section 10: Confidence score
# ===========================================================================

class TestConfidenceScore:
    def test_full_data_high_confidence(self, engine):
        out = engine.evaluate(_base_input(
            prediction_confidence=0.95,
            observation_count=500,
            hours_since_last_reading=0.5,
        ))
        assert out.confidence >= 0.90

    def test_no_predictions_low_confidence(self, engine):
        out = engine.evaluate(_base_input(
            failure_probability=None,
            rul_hours=None,
            anomaly_score=None,
        ))
        assert out.confidence < 0.60

    def test_stale_sensor_reduces_confidence(self, engine):
        high_conf = engine.evaluate(_base_input(stale_sensor_codes=[]))
        low_conf = engine.evaluate(_base_input(stale_sensor_codes=["S1", "S2"]))
        assert low_conf.confidence < high_conf.confidence

    def test_confidence_never_below_floor(self, engine):
        """Confidence floor is 0.05 — never zero or negative."""
        out = engine.evaluate(_base_input(
            failure_probability=None,
            rul_hours=None,
            anomaly_score=None,
            observation_count=0,
            prediction_confidence=0.01,
            hours_since_last_reading=9999.0,
            stale_sensor_codes=["S1", "S2", "S3"],
        ))
        assert out.confidence >= 0.05

    def test_confidence_never_above_ceiling(self, engine):
        out = engine.evaluate(_base_input(
            prediction_confidence=0.99,
            observation_count=1000,
        ))
        assert out.confidence <= 1.0


# ===========================================================================
# Section 11: Spec §18 edge cases (14 from ARCHITECTURE.md)
# ===========================================================================

class TestSpecEdgeCases:
    """Each test maps directly to a named edge case in the architecture spec."""

    # EC-1: Missing telemetry → UNKNOWN
    def test_ec1_missing_telemetry_unknown(self, engine):
        out = engine.evaluate(_base_input(
            failure_probability=None,
            rul_hours=None,
            anomaly_score=None,
            observation_count=0,
        ))
        assert out.status == ReadinessStatus.UNKNOWN

    # EC-2: Stale sensor → UNKNOWN
    def test_ec2_stale_sensor_unknown(self, engine):
        out = engine.evaluate(_base_input(hours_since_last_reading=12.0))
        assert out.status == ReadinessStatus.UNKNOWN

    # EC-3: Outlier (high anomaly, low failure risk) → AT_RISK, not NOT_READY
    def test_ec3_outlier_at_risk_not_not_ready(self, engine):
        out = engine.evaluate(_base_input(
            anomaly_score=0.95,
            failure_probability=0.04,
        ))
        assert out.status == ReadinessStatus.AT_RISK
        assert out.status != ReadinessStatus.NOT_READY

    # EC-4: Sensor drift → AT_RISK
    def test_ec4_sensor_drift_at_risk(self, engine):
        out = engine.evaluate(_base_input(drifting_sensor_codes=["TEMP-02"]))
        assert out.status == ReadinessStatus.AT_RISK
        assert ReasonCode.SENSOR_DRIFT in _reason_codes(out)

    # EC-5: Duplicate timestamp (handled gracefully — engine accepts pre-processed inputs)
    def test_ec5_duplicate_timestamp_graceful(self, engine):
        """Engine receives pre-processed inputs; same evaluated_at twice doesn't crash."""
        inp = _base_input()
        out1 = engine.evaluate(inp)
        out2 = engine.evaluate(inp)
        assert out1.status == out2.status  # deterministic

    # EC-6: Asset under maintenance → NOT_READY
    def test_ec6_asset_under_maintenance_not_ready(self, engine):
        out = engine.evaluate(_base_input(
            maintenance_status=MaintenanceStatus.UNDER_MAINTENANCE,
        ))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.ASSET_UNDER_MAINTENANCE

    # EC-7: RUL below mission duration → NOT_READY
    def test_ec7_rul_below_mission_duration_not_ready(self, engine):
        out = engine.evaluate(_base_input(
            rul_hours=5.0,
            mission_duration_hours=8.0,  # 5 < 8 * 1.25 = 10
        ))
        assert out.status == ReadinessStatus.NOT_READY
        assert out.primary_reason == ReasonCode.RUL_BELOW_MISSION_REQUIREMENT

    # EC-8: High anomaly + low failure risk → AT_RISK (investigate, not auto NOT_READY)
    def test_ec8_high_anomaly_low_risk_at_risk(self, engine):
        out = engine.evaluate(_base_input(
            anomaly_score=0.92,
            failure_probability=0.07,
        ))
        assert out.status == ReadinessStatus.AT_RISK

    # EC-9: High failure risk + poor data quality → lower confidence, UNKNOWN
    def test_ec9_high_risk_poor_quality_unknown(self, engine):
        out = engine.evaluate(_base_input(
            failure_probability=0.30,
            prediction_confidence=0.25,
        ))
        assert out.status == ReadinessStatus.UNKNOWN
        assert out.confidence < 0.70

    # EC-10: Maintenance recovery → readiness re-evaluated
    def test_ec10_maintenance_recovery_becomes_ready(self, engine):
        """After maintenance, if all metrics are healthy, asset re-attains READY."""
        out = engine.evaluate(_base_input(
            maintenance_status=MaintenanceStatus.RETURNED_TO_SERVICE,
            failure_probability=0.03,
            rul_hours=800.0,
            anomaly_score=0.10,
        ))
        assert out.status == ReadinessStatus.READY

    # EC-11: Right-censored asset → UNKNOWN
    def test_ec11_right_censored_no_prediction_unknown(self, engine):
        """No prediction record for a newly commissioned asset."""
        out = engine.evaluate(_base_input(
            failure_probability=None,
            rul_hours=None,
            anomaly_score=None,
            observation_count=2,
        ))
        assert out.status == ReadinessStatus.UNKNOWN

    # EC-12: Mission conflict → NOT_READY (blocking work order used as proxy)
    def test_ec12_mission_conflict_not_ready(self, engine):
        """Blocking work order represents a mission-conflict lock."""
        out = engine.evaluate(_base_input(
            has_blocking_work_order=True,
            blocking_work_order_ids=["WO-CONFLICT-001"],
        ))
        assert out.status == ReadinessStatus.NOT_READY

    # EC-13: Overdue maintenance → AT_RISK or NOT_READY per criticality
    def test_ec13a_overdue_critical_maintenance_not_ready(self, engine):
        out = engine.evaluate(_base_input(
            maintenance_is_critical=True,
            maintenance_overdue_hours=72.0,
        ))
        assert out.status == ReadinessStatus.NOT_READY

    def test_ec13b_overdue_routine_maintenance_at_risk(self, engine):
        out = engine.evaluate(_base_input(
            maintenance_is_critical=False,
            maintenance_overdue_hours=5.0,
        ))
        assert out.status == ReadinessStatus.AT_RISK

    # EC-14: Sensor failure vs component failure — distinguish in reason_code
    def test_ec14_sensor_fault_vs_component_failure_distinct_codes(self, engine):
        """SENSOR_FAULT_DETECTED and CRITICAL_COMPONENT_FAILURE are distinct reason codes."""
        sensor_out = engine.evaluate(_base_input(
            fault_sensor_codes=["TEMP-SENSOR-01"],
            component_states={"ENGINE_CORE": ComponentState.NOMINAL},
        ))
        comp_out = engine.evaluate(_base_input(
            fault_sensor_codes=[],
            component_states={"ENGINE_CORE": ComponentState.FAILED},
        ))
        sensor_codes = _reason_codes(sensor_out)
        comp_codes = _reason_codes(comp_out)

        assert ReasonCode.SENSOR_FAULT_DETECTED in sensor_codes
        assert ReasonCode.CRITICAL_COMPONENT_FAILURE not in sensor_codes
        assert ReasonCode.CRITICAL_COMPONENT_FAILURE in comp_codes
        assert ReasonCode.SENSOR_FAULT_DETECTED not in comp_codes

        # Both have different primary reasons
        assert sensor_out.primary_reason == ReasonCode.SENSOR_FAULT_DETECTED
        assert comp_out.primary_reason == ReasonCode.CRITICAL_COMPONENT_FAILURE


# ===========================================================================
# Section 12: Evidence content quality
# ===========================================================================

class TestEvidenceContent:
    def test_every_factor_has_code_message_severity(self, engine):
        """All contributing factors must have code, message, and severity."""
        for scenario in [
            _base_input(),
            _base_input(has_blocking_work_order=True),
            _base_input(failure_probability=None, rul_hours=None, anomaly_score=None),
            _base_input(failure_probability=0.25),
            _base_input(anomaly_score=0.85),
        ]:
            out = engine.evaluate(scenario)
            for factor in out.contributing_factors:
                assert isinstance(factor.code, ReasonCode)
                assert isinstance(factor.message, str) and len(factor.message) > 0
                assert factor.severity in {"critical", "warning", "info"}

    def test_ready_output_has_one_info_factor(self, engine):
        out = engine.evaluate(_base_input())
        assert len(out.contributing_factors) == 1
        assert out.contributing_factors[0].severity == "info"

    def test_not_ready_factors_are_critical_severity(self, engine):
        out = engine.evaluate(_base_input(has_blocking_work_order=True))
        r1_factor = next(f for f in out.contributing_factors
                         if f.code == ReasonCode.CRITICAL_MAINTENANCE_OPEN)
        assert r1_factor.severity == "critical"

    def test_at_risk_factors_are_warning_severity(self, engine):
        out = engine.evaluate(_base_input(failure_probability=0.25))
        r8_factor = next(f for f in out.contributing_factors
                         if f.code == ReasonCode.ELEVATED_FAILURE_PROBABILITY)
        assert r8_factor.severity == "warning"

    def test_evidence_dict_contains_relevant_values(self, engine):
        out = engine.evaluate(_base_input(failure_probability=0.50))
        factor = next(f for f in out.contributing_factors
                      if f.code == ReasonCode.HIGH_FAILURE_PROBABILITY)
        assert "failure_probability" in factor.evidence
        assert factor.evidence["failure_probability"] == pytest.approx(0.50)
        assert "threshold" in factor.evidence

    def test_rul_factor_includes_mission_duration(self, engine):
        out = engine.evaluate(_base_input(rul_hours=5.0, mission_duration_hours=8.0))
        factor = next(f for f in out.contributing_factors
                      if f.code == ReasonCode.RUL_BELOW_MISSION_REQUIREMENT)
        assert "mission_duration_hours" in factor.evidence
        assert "rul_hours" in factor.evidence


# ===========================================================================
# Section 13: Boundary and edge values
# ===========================================================================

class TestBoundaryValues:
    def test_failure_prob_zero_ready(self, engine):
        out = engine.evaluate(_base_input(failure_probability=0.0))
        assert out.status == ReadinessStatus.READY

    def test_failure_prob_one_not_ready(self, engine):
        out = engine.evaluate(_base_input(failure_probability=1.0))
        assert out.status == ReadinessStatus.NOT_READY

    def test_rul_zero_not_ready_when_mission_exists(self, engine):
        out = engine.evaluate(_base_input(rul_hours=0.0, mission_duration_hours=1.0))
        assert out.status == ReadinessStatus.NOT_READY

    def test_rul_very_large_ready(self, engine):
        out = engine.evaluate(_base_input(rul_hours=100_000.0))
        assert out.status == ReadinessStatus.READY

    def test_mission_duration_zero_rul_not_checked(self, engine):
        """No mission duration means no RUL-based check."""
        out = engine.evaluate(_base_input(
            rul_hours=0.0,
            mission_duration_hours=0.0,
        ))
        # Should not trigger RUL checks; might be READY or AT_RISK from other inputs
        assert ReasonCode.RUL_BELOW_MISSION_REQUIREMENT not in _reason_codes(out)

    def test_empty_component_states_does_not_crash(self, engine):
        out = engine.evaluate(_base_input(component_states={}))
        assert out.status in ReadinessStatus

    def test_empty_critical_components_no_r3(self, engine):
        """No critical components defined → R3 cannot fire."""
        out = engine.evaluate(_base_input(
            component_states={"ENGINE_CORE": ComponentState.FAILED},
            critical_components=set(),
        ))
        assert ReasonCode.CRITICAL_COMPONENT_FAILURE not in _reason_codes(out)

    def test_anomaly_score_exactly_at_threshold_not_triggered(self, engine):
        out = engine.evaluate(_base_input(anomaly_score=0.70))
        assert ReasonCode.ANOMALY_DETECTED not in _reason_codes(out)

    def test_observation_count_negative_treated_as_insufficient(self, engine):
        """Negative observation count is treated as < min_observations."""
        out = engine.evaluate(_base_input(observation_count=-1))
        assert ReasonCode.INSUFFICIENT_DATA in _reason_codes(out)

    def test_all_component_states_nominal(self, engine):
        out = engine.evaluate(_base_input(
            component_states={
                "ENG": ComponentState.NOMINAL,
                "ROTOR": ComponentState.NOMINAL,
                "GEAR": ComponentState.NOMINAL,
            },
            critical_components={"ENG", "ROTOR", "GEAR"},
        ))
        assert out.status == ReadinessStatus.READY

    def test_component_fault_on_non_critical_not_r3(self, engine):
        out = engine.evaluate(_base_input(
            component_states={"CABIN_LIGHT": ComponentState.FAILED},
            critical_components={"ENGINE_CORE"},
        ))
        assert ReasonCode.CRITICAL_COMPONENT_FAILURE not in _reason_codes(out)

    def test_hours_since_reading_none_no_stale_flag(self, engine):
        out = engine.evaluate(_base_input(
            hours_since_last_reading=None,
            stale_sensor_codes=[],
        ))
        assert ReasonCode.STALE_CRITICAL_TELEMETRY not in _reason_codes(out)
