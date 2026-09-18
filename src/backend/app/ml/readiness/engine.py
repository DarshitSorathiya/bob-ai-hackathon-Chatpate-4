"""
ReadinessEngine — deterministic, rule-based, explainable readiness classification.

Design principles:
  1. NO LLM, NO random numbers, NO external I/O.
  2. Same inputs always produce the same outputs (deterministic).
  3. Every decision traces to a named rule and a ReasonCode.
  4. UNKNOWN != READY.  Callers must never promote UNKNOWN to operational use.
  5. Rules are ordered by priority; the first matching blocking rule wins,
     but ALL factors are collected to provide a complete explanation.
  6. Thresholds are externalised in ReadinessThresholds; defaults are safe/conservative.

Rule Precedence (highest → lowest priority):
  ── NOT_READY rules ─────────────────────────────────────────────────────────
  R1   CRITICAL_MAINTENANCE_OPEN       — blocking work order exists
  R2   ASSET_UNDER_MAINTENANCE         — maintenance currently in progress
  R3   CRITICAL_COMPONENT_FAILURE      — critical component in FAILED state
  R4a  SENSOR_FAULT_DETECTED           — critical sensor has a hardware fault
  R4b  OVERDUE_CRITICAL_MAINTENANCE    — critical maintenance past due by > threshold
  R5   HIGH_FAILURE_PROBABILITY        — P(failure) > not_ready_failure_prob
  R6   RUL_BELOW_MISSION_REQUIREMENT   — RUL * safety_margin < mission_duration

  ── UNKNOWN rules ────────────────────────────────────────────────────────────
  R7a  NO_PREDICTION_AVAILABLE         — no ML prediction record at all
  R7b  INSUFFICIENT_DATA               — fewer observations than minimum
  R7c  LOW_PREDICTION_CONFIDENCE       — model confidence < threshold
  R7d  STALE_CRITICAL_TELEMETRY        — last reading too old
  R7e  PREDICTION_DATA_QUALITY_DEGRADED — high fail prob + poor data quality

  ── AT_RISK rules ────────────────────────────────────────────────────────────
  R8   ELEVATED_FAILURE_PROBABILITY    — P(failure) > at_risk_failure_prob
  R9   RUL_WITHIN_SAFETY_MARGIN        — RUL below 2× mission duration
  R10  ANOMALY_DETECTED                — anomaly_score above threshold
  R11  SENSOR_DRIFT                    — one or more sensors drifting
  R12  OVERDUE_ROUTINE_MAINTENANCE     — routine maintenance is overdue

  ── READY ─────────────────────────────────────────────────────────────────────
  R13  ALL_CHECKS_PASSED               — nothing triggered above

Confidence calculation:
  Starts at 1.0.  Each degrading factor reduces confidence:
  - No prediction:            -0.50
  - Low observation count:    -0.30
  - Low model confidence:     penalty = (threshold - actual) / threshold * 0.40
  - Stale telemetry:          -0.20 per stale critical sensor (capped at -0.40)
  - Poor data quality:        -0.15
  Clamped to [0.05, 1.0].
"""

from __future__ import annotations

from datetime import datetime

from app.ml.readiness.models import (
    ComponentState,
    ContributingFactor,
    MaintenanceStatus,
    ReadinessInput,
    ReadinessOutput,
    ReadinessStatus,
    ReadinessThresholds,
    ReasonCode,
)


class ReadinessEngine:
    """Deterministic readiness classifier.

    Usage::

        engine = ReadinessEngine()
        result = engine.evaluate(inp)

    Inject custom thresholds for environment-specific policy::

        engine = ReadinessEngine(thresholds=ReadinessThresholds(not_ready_failure_prob=0.35))
    """

    def __init__(self, thresholds: ReadinessThresholds | None = None) -> None:
        self._thresholds = thresholds or ReadinessThresholds()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, inp: ReadinessInput) -> ReadinessOutput:
        """Evaluate readiness for a single asset against a mission window.

        Args:
            inp: Fully populated ReadinessInput.

        Returns:
            ReadinessOutput with status, primary reason, all contributing
            factors, and the thresholds that were in effect.
        """
        t = self._thresholds
        factors: list[ContributingFactor] = []

        # ----------------------------------------------------------------
        # Phase 1: Collect ALL contributing factors (do not short-circuit)
        # ----------------------------------------------------------------
        not_ready_factors: list[ContributingFactor] = []
        unknown_factors: list[ContributingFactor] = []
        at_risk_factors: list[ContributingFactor] = []

        # --- R1: Blocking work order ----------------------------------------
        if inp.has_blocking_work_order:
            not_ready_factors.append(ContributingFactor(
                code=ReasonCode.CRITICAL_MAINTENANCE_OPEN,
                message=(
                    f"Asset {inp.asset_code} has {len(inp.blocking_work_order_ids)} "
                    f"open blocking work order(s): {', '.join(inp.blocking_work_order_ids) or 'unknown'}"
                ),
                severity="critical",
                evidence={
                    "blocking_work_order_ids": inp.blocking_work_order_ids,
                    "count": len(inp.blocking_work_order_ids),
                },
            ))

        # --- R2: Under maintenance -------------------------------------------
        if inp.maintenance_status == MaintenanceStatus.UNDER_MAINTENANCE:
            not_ready_factors.append(ContributingFactor(
                code=ReasonCode.ASSET_UNDER_MAINTENANCE,
                message=f"Asset {inp.asset_code} is currently under maintenance.",
                severity="critical",
                evidence={"maintenance_status": inp.maintenance_status.value},
            ))

        # --- R3: Critical component failure ----------------------------------
        failed_critical = [
            code for code, state in inp.component_states.items()
            if state == ComponentState.FAILED and code in inp.critical_components
        ]
        if failed_critical:
            not_ready_factors.append(ContributingFactor(
                code=ReasonCode.CRITICAL_COMPONENT_FAILURE,
                message=(
                    f"Critical component(s) in FAILED state: "
                    f"{', '.join(sorted(failed_critical))}"
                ),
                severity="critical",
                evidence={
                    "failed_components": sorted(failed_critical),
                    "critical_components": sorted(inp.critical_components),
                },
            ))

        # --- R4a: Sensor fault (critical sensors only) -----------------------
        if inp.fault_sensor_codes:
            not_ready_factors.append(ContributingFactor(
                code=ReasonCode.SENSOR_FAULT_DETECTED,
                message=(
                    f"Sensor fault detected on: "
                    f"{', '.join(sorted(inp.fault_sensor_codes))}. "
                    "Telemetry from these sensors is invalid."
                ),
                severity="critical",
                evidence={"fault_sensors": sorted(inp.fault_sensor_codes)},
            ))

        # --- R4b: Overdue critical maintenance --------------------------------
        if inp.maintenance_is_critical and inp.maintenance_overdue_hours > t.critical_overdue_hours:
            not_ready_factors.append(ContributingFactor(
                code=ReasonCode.OVERDUE_CRITICAL_MAINTENANCE,
                message=(
                    f"Critical maintenance is {inp.maintenance_overdue_hours:.1f} h overdue "
                    f"(threshold: {t.critical_overdue_hours:.1f} h)."
                ),
                severity="critical",
                evidence={
                    "hours_overdue": inp.maintenance_overdue_hours,
                    "threshold_hours": t.critical_overdue_hours,
                    "is_critical": True,
                },
            ))

        # --- R5: High failure probability ------------------------------------
        if inp.failure_probability is not None and inp.failure_probability > t.not_ready_failure_prob:
            not_ready_factors.append(ContributingFactor(
                code=ReasonCode.HIGH_FAILURE_PROBABILITY,
                message=(
                    f"Failure probability {inp.failure_probability:.1%} exceeds NOT_READY "
                    f"threshold {t.not_ready_failure_prob:.1%}."
                ),
                severity="critical",
                evidence={
                    "failure_probability": inp.failure_probability,
                    "threshold": t.not_ready_failure_prob,
                },
            ))

        # --- R6: RUL below mission requirement (with safety margin) ----------
        if (
            inp.rul_hours is not None
            and inp.mission_duration_hours > 0
            and inp.rul_hours < inp.mission_duration_hours * t.not_ready_rul_margin
        ):
            not_ready_factors.append(ContributingFactor(
                code=ReasonCode.RUL_BELOW_MISSION_REQUIREMENT,
                message=(
                    f"RUL estimate {inp.rul_hours:.1f} h is below the required "
                    f"{inp.mission_duration_hours * t.not_ready_rul_margin:.1f} h "
                    f"(mission {inp.mission_duration_hours:.1f} h × "
                    f"{t.not_ready_rul_margin:.2f} safety margin)."
                ),
                severity="critical",
                evidence={
                    "rul_hours": inp.rul_hours,
                    "mission_duration_hours": inp.mission_duration_hours,
                    "safety_margin": t.not_ready_rul_margin,
                    "required_rul": inp.mission_duration_hours * t.not_ready_rul_margin,
                    "rul_lower": inp.rul_lower,
                    "rul_upper": inp.rul_upper,
                },
            ))

        # --- R7a: No prediction available ------------------------------------
        missing_prediction_types = [
            name for name, value in (
                ("failure risk", inp.failure_probability),
                ("remaining useful life", inp.rul_hours),
            )
            if value is None
        ]
        if missing_prediction_types:
            unknown_factors.append(ContributingFactor(
                code=ReasonCode.NO_PREDICTION_AVAILABLE,
                message=(
                    f"Required ML prediction(s) missing for asset {inp.asset_code}: "
                    f"{', '.join(missing_prediction_types)}. "
                    "Cannot establish mission readiness."
                ),
                severity="warning",
                evidence={
                    "asset_id": inp.asset_id,
                    "missing_prediction_types": missing_prediction_types,
                },
            ))

        # --- R7b: Insufficient observations ----------------------------------
        if (
            inp.observation_count is not None
            and inp.observation_count < t.min_observations
        ):
            unknown_factors.append(ContributingFactor(
                code=ReasonCode.INSUFFICIENT_DATA,
                message=(
                    f"Only {inp.observation_count} observations available; "
                    f"minimum required: {t.min_observations}."
                ),
                severity="warning",
                evidence={
                    "observation_count": inp.observation_count,
                    "min_required": t.min_observations,
                },
            ))

        # --- R7c: Low model confidence ---------------------------------------
        if (
            inp.prediction_confidence is not None
            and inp.prediction_confidence < t.min_confidence
        ):
            unknown_factors.append(ContributingFactor(
                code=ReasonCode.LOW_PREDICTION_CONFIDENCE,
                message=(
                    f"Model confidence {inp.prediction_confidence:.1%} is below the "
                    f"minimum threshold {t.min_confidence:.1%}."
                ),
                severity="warning",
                evidence={
                    "confidence": inp.prediction_confidence,
                    "threshold": t.min_confidence,
                },
            ))

        # --- R7d: Stale critical telemetry -----------------------------------
        stale_flag = (
            inp.hours_since_last_reading is not None
            and inp.hours_since_last_reading > t.stale_hours
        )
        if stale_flag or inp.stale_sensor_codes:
            unknown_factors.append(ContributingFactor(
                code=ReasonCode.STALE_CRITICAL_TELEMETRY,
                message=(
                    f"Critical telemetry is stale. "
                    f"Last reading: {inp.hours_since_last_reading:.1f} h ago "
                    f"(threshold: {t.stale_hours:.1f} h). "
                    + (
                        f"Stale sensors: {', '.join(sorted(inp.stale_sensor_codes))}."
                        if inp.stale_sensor_codes else ""
                    )
                ),
                severity="warning",
                evidence={
                    "hours_since_last_reading": inp.hours_since_last_reading,
                    "stale_threshold_hours": t.stale_hours,
                    "stale_sensor_codes": sorted(inp.stale_sensor_codes),
                },
            ))

        # --- R7e: High failure prob + poor data quality ----------------------
        if (
            inp.failure_probability is not None
            and inp.failure_probability > t.at_risk_failure_prob
            and inp.prediction_confidence is not None
            and inp.prediction_confidence < t.min_confidence
        ):
            unknown_factors.append(ContributingFactor(
                code=ReasonCode.PREDICTION_DATA_QUALITY_DEGRADED,
                message=(
                    f"Elevated failure probability ({inp.failure_probability:.1%}) "
                    f"combined with low model confidence ({inp.prediction_confidence:.1%}); "
                    "result is not reliable."
                ),
                severity="warning",
                evidence={
                    "failure_probability": inp.failure_probability,
                    "confidence": inp.prediction_confidence,
                    "min_confidence": t.min_confidence,
                },
            ))

        # --- R8: Elevated failure probability (AT_RISK) ----------------------
        if (
            inp.failure_probability is not None
            and t.at_risk_failure_prob < inp.failure_probability <= t.not_ready_failure_prob
        ):
            at_risk_factors.append(ContributingFactor(
                code=ReasonCode.ELEVATED_FAILURE_PROBABILITY,
                message=(
                    f"Failure probability {inp.failure_probability:.1%} is above the "
                    f"AT_RISK threshold {t.at_risk_failure_prob:.1%}."
                ),
                severity="warning",
                evidence={
                    "failure_probability": inp.failure_probability,
                    "at_risk_threshold": t.at_risk_failure_prob,
                    "not_ready_threshold": t.not_ready_failure_prob,
                },
            ))

        # --- R9: RUL within safety margin (AT_RISK) --------------------------
        if (
            inp.rul_hours is not None
            and inp.mission_duration_hours > 0
        ):
            min_not_ready = inp.mission_duration_hours * t.not_ready_rul_margin
            min_at_risk = inp.mission_duration_hours * t.at_risk_rul_margin
            if min_not_ready <= inp.rul_hours < min_at_risk:
                at_risk_factors.append(ContributingFactor(
                    code=ReasonCode.RUL_WITHIN_SAFETY_MARGIN,
                    message=(
                        f"RUL {inp.rul_hours:.1f} h is within the AT_RISK safety margin "
                        f"(< {min_at_risk:.1f} h = {t.at_risk_rul_margin:.1f}× mission duration)."
                    ),
                    severity="warning",
                    evidence={
                        "rul_hours": inp.rul_hours,
                        "mission_duration_hours": inp.mission_duration_hours,
                        "at_risk_margin": t.at_risk_rul_margin,
                        "required_rul_at_risk": min_at_risk,
                    },
                ))

        # --- R10: Anomaly detected (AT_RISK) ---------------------------------
        if (
            inp.anomaly_score is not None
            and inp.anomaly_score > t.at_risk_anomaly_score
        ):
            at_risk_factors.append(ContributingFactor(
                code=ReasonCode.ANOMALY_DETECTED,
                message=(
                    f"Anomaly score {inp.anomaly_score:.3f} exceeds AT_RISK threshold "
                    f"{t.at_risk_anomaly_score:.3f}. "
                    "Root cause not yet determined; treat as advisory."
                ),
                severity="warning",
                evidence={
                    "anomaly_score": inp.anomaly_score,
                    "threshold": t.at_risk_anomaly_score,
                },
            ))

        # --- R11: Sensor drift -----------------------------------------------
        if inp.drifting_sensor_codes:
            at_risk_factors.append(ContributingFactor(
                code=ReasonCode.SENSOR_DRIFT,
                message=(
                    f"Sensor drift detected outside nominal range on: "
                    f"{', '.join(sorted(inp.drifting_sensor_codes))}."
                ),
                severity="warning",
                evidence={"drifting_sensors": sorted(inp.drifting_sensor_codes)},
            ))

        # --- R12: Overdue routine maintenance --------------------------------
        if (
            not inp.maintenance_is_critical
            and inp.maintenance_overdue_hours > t.routine_overdue_hours
        ):
            at_risk_factors.append(ContributingFactor(
                code=ReasonCode.OVERDUE_ROUTINE_MAINTENANCE,
                message=(
                    f"Routine maintenance is {inp.maintenance_overdue_hours:.1f} h overdue."
                ),
                severity="info",
                evidence={
                    "hours_overdue": inp.maintenance_overdue_hours,
                    "is_critical": False,
                },
            ))

        # ----------------------------------------------------------------
        # Phase 2: Determine final status by priority
        # ----------------------------------------------------------------
        all_factors = not_ready_factors + unknown_factors + at_risk_factors

        if not_ready_factors:
            status = ReadinessStatus.NOT_READY
            primary_reason = not_ready_factors[0].code
            factors = all_factors
        elif unknown_factors:
            status = ReadinessStatus.UNKNOWN
            primary_reason = unknown_factors[0].code
            factors = all_factors
        elif at_risk_factors:
            status = ReadinessStatus.AT_RISK
            primary_reason = at_risk_factors[0].code
            factors = at_risk_factors
        else:
            status = ReadinessStatus.READY
            primary_reason = ReasonCode.ALL_CHECKS_PASSED
            factors = [ContributingFactor(
                code=ReasonCode.ALL_CHECKS_PASSED,
                message=f"Asset {inp.asset_code} passed all readiness checks.",
                severity="info",
                evidence={
                    "failure_probability": inp.failure_probability,
                    "rul_hours": inp.rul_hours,
                    "mission_duration_hours": inp.mission_duration_hours,
                },
            )]

        # ----------------------------------------------------------------
        # Phase 3: Compute confidence score
        # ----------------------------------------------------------------
        confidence = self._compute_confidence(inp, unknown_factors, t)

        return ReadinessOutput(
            status=status,
            primary_reason=primary_reason,
            contributing_factors=factors,
            confidence=confidence,
            evaluated_at=inp.evaluated_at,
            asset_id=inp.asset_id,
            asset_code=inp.asset_code,
            mission_id=inp.mission_id,
            thresholds_used=t,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_confidence(
        inp: ReadinessInput,
        unknown_factors: list[ContributingFactor],
        t: ReadinessThresholds,
    ) -> float:
        """Compute confidence in the readiness classification.

        Confidence starts at 1.0 and is penalised for missing or degraded
        evidence.  The final value is clamped to [0.05, 1.0].
        """
        confidence = 1.0

        # No prediction record at all
        if inp.failure_probability is None and inp.rul_hours is None:
            confidence -= 0.50

        # Insufficient observations
        if inp.observation_count is not None and inp.observation_count < t.min_observations:
            fraction_missing = 1.0 - inp.observation_count / t.min_observations
            confidence -= 0.30 * fraction_missing

        # Low model confidence
        if inp.prediction_confidence is not None and inp.prediction_confidence < t.min_confidence:
            confidence -= (t.min_confidence - inp.prediction_confidence) / t.min_confidence * 0.40

        # Stale telemetry (up to -0.40 for multiple stale sensors)
        stale_penalty = min(len(inp.stale_sensor_codes) * 0.20, 0.40)
        if inp.hours_since_last_reading is not None and inp.hours_since_last_reading > t.stale_hours:
            stale_penalty = max(stale_penalty, 0.20)
        confidence -= stale_penalty

        # Data quality degraded
        if any(f.code == ReasonCode.PREDICTION_DATA_QUALITY_DEGRADED for f in unknown_factors):
            confidence -= 0.15

        return max(0.05, min(1.0, confidence))
