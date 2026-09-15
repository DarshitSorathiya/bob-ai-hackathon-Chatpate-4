"""
MaintenancePrioritizer — deterministic, explainable maintenance queue.

Priority formula
----------------
priority_score = (
      w_risk     * failure_risk_score        # 0.30
    + w_rul      * rul_score                 # 0.20
    + w_mission  * mission_proximity_score   # 0.20
    + w_asset    * asset_criticality_score   # 0.10
    + w_comp     * component_criticality_score  # 0.10
    + w_safety   * safety_score              # 0.05
    + w_overdue  * overdue_score             # 0.05
)

All sub-scores are normalised to [0, 1].

Sub-score definitions
---------------------
failure_risk_score:
    = failure_probability if available, else 0.5 * anomaly_score (fallback)

rul_score:
    = 0.0 if rul > 200 h
    = 1.0 if rul <= 0
    = 1 - rul/200 otherwise (linear decay)
    If rul is None and mission is scheduled: 0.50 (conservative)
    If rul is None and no mission: 0.25

mission_proximity_score:
    = 0.0 if no mission scheduled
    = 1.0 if blocks_mission=True and hours_until_mission < downtime_estimate
    = 1 - hours_until_mission/200 (linear decay, capped at [0,1])

asset_criticality_score:
    CRITICAL → 1.0, HIGH → 0.75, MEDIUM → 0.50, LOW → 0.25

component_criticality_score:
    SAFETY_CRITICAL → 1.0, MISSION_CRITICAL → 0.75, OPERATIONAL → 0.40, NON_ESSENTIAL → 0.15

safety_score:
    AIRWORTHINESS_LIMITING → 1.0, SAFETY_OF_FLIGHT → 0.85,
    SAFETY_RISK → 0.50, NO_SAFETY_IMPLICATION → 0.0

overdue_score:
    = min(1.0, hours_overdue / 200.0)   (linear, capped)

Urgency thresholds:
    [0.80, 1.0] → IMMEDIATE
    [0.60, 0.80) → URGENT
    [0.40, 0.60) → SCHEDULED
    [0.20, 0.40) → ROUTINE
    [0.00, 0.20) → DEFERRED

Safety override:
    AIRWORTHINESS_LIMITING → always IMMEDIATE
    SAFETY_OF_FLIGHT        → always at least URGENT
"""

from __future__ import annotations

from datetime import datetime

from app.ml.maintenance.models import (
    AssetCriticality,
    ComponentCriticality,
    MaintenanceItem,
    MaintenanceQueue,
    MaintenanceState,
    PrioritizedItem,
    SafetyClassification,
    ScoreBreakdown,
    UrgencyLevel,
)

# Weights
_W_RISK = 0.30
_W_RUL = 0.20
_W_MISSION = 0.20
_W_ASSET = 0.10
_W_COMP = 0.10
_W_SAFETY = 0.05
_W_OVERDUE = 0.05

_ASSET_SCORES: dict[AssetCriticality, float] = {
    AssetCriticality.CRITICAL: 1.0,
    AssetCriticality.HIGH: 0.75,
    AssetCriticality.MEDIUM: 0.50,
    AssetCriticality.LOW: 0.25,
}

_COMP_SCORES: dict[ComponentCriticality, float] = {
    ComponentCriticality.SAFETY_CRITICAL: 1.0,
    ComponentCriticality.MISSION_CRITICAL: 0.75,
    ComponentCriticality.OPERATIONAL: 0.40,
    ComponentCriticality.NON_ESSENTIAL: 0.15,
}

_SAFETY_SCORES: dict[SafetyClassification, float] = {
    SafetyClassification.AIRWORTHINESS_LIMITING: 1.0,
    SafetyClassification.SAFETY_OF_FLIGHT: 0.85,
    SafetyClassification.SAFETY_RISK: 0.50,
    SafetyClassification.NO_SAFETY_IMPLICATION: 0.0,
}


class MaintenancePrioritizer:
    """Deterministic maintenance queue generator.

    Usage::

        prioritizer = MaintenancePrioritizer()
        queue = prioritizer.prioritize(items, evaluated_at)
    """

    def prioritize(
        self,
        items: list[MaintenanceItem],
        evaluated_at: datetime,
    ) -> MaintenanceQueue:
        """Compute priority scores and return a ranked queue.

        Args:
            items:        List of maintenance candidates.
            evaluated_at: Timestamp for this evaluation.

        Returns:
            MaintenanceQueue sorted by priority_score descending.
        """
        prioritized: list[PrioritizedItem] = [
            self._score_item(item) for item in items
        ]
        prioritized.sort(key=lambda x: x.priority_score, reverse=True)

        return MaintenanceQueue(
            items=prioritized,
            evaluated_at=evaluated_at,
            total_immediate=sum(1 for i in prioritized if i.urgency_level == UrgencyLevel.IMMEDIATE),
            total_urgent=sum(1 for i in prioritized if i.urgency_level == UrgencyLevel.URGENT),
            total_scheduled=sum(1 for i in prioritized if i.urgency_level == UrgencyLevel.SCHEDULED),
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _score_item(self, item: MaintenanceItem) -> PrioritizedItem:
        """Compute all sub-scores and aggregate."""
        factors: list[tuple[str, str]] = []

        # --- Failure risk ---
        risk_score = self._failure_risk_score(item)
        if item.failure_probability is not None:
            factors.append(("FAILURE_PROBABILITY", f"{item.failure_probability:.1%}"))
        elif item.anomaly_score is not None:
            factors.append(("ANOMALY_SCORE", f"{item.anomaly_score:.3f} (fallback for missing failure probability)"))

        # --- RUL ---
        rul_score = self._rul_score(item)
        if item.rul_hours is not None:
            factors.append(("RUL_HOURS", f"{item.rul_hours:.1f} h"))
        else:
            factors.append(("RUL_UNKNOWN", "RUL not available; conservative score applied"))

        # --- Mission proximity ---
        mission_score = self._mission_proximity_score(item)
        if item.hours_until_next_mission is not None:
            factors.append((
                "MISSION_PROXIMITY",
                f"{item.hours_until_next_mission:.1f} h until next mission"
                + (" [BLOCKS MISSION]" if item.blocks_mission else ""),
            ))
        if item.blocks_mission:
            factors.append(("BLOCKS_MISSION", f"This item blocks mission assignment for {item.asset_code}"))

        # --- Asset criticality ---
        asset_score = _ASSET_SCORES[item.asset_criticality]
        factors.append(("ASSET_CRITICALITY", item.asset_criticality.value))

        # --- Component criticality ---
        comp_score = _COMP_SCORES[item.component_criticality]
        factors.append(("COMPONENT_CRITICALITY", item.component_criticality.value))

        # --- Safety ---
        safety_score = _SAFETY_SCORES[item.safety_classification]
        if safety_score > 0:
            factors.append(("SAFETY_CLASSIFICATION", item.safety_classification.value))

        # --- Overdue ---
        overdue_score = min(1.0, item.hours_overdue / 200.0)
        if item.hours_overdue > 0:
            factors.append(("OVERDUE_HOURS", f"{item.hours_overdue:.1f} h overdue"))

        # --- Aggregate ---
        total = (
            _W_RISK * risk_score
            + _W_RUL * rul_score
            + _W_MISSION * mission_score
            + _W_ASSET * asset_score
            + _W_COMP * comp_score
            + _W_SAFETY * safety_score
            + _W_OVERDUE * overdue_score
        )
        total = round(min(1.0, max(0.0, total)), 4)

        breakdown = ScoreBreakdown(
            failure_risk_score=round(risk_score, 4),
            rul_score=round(rul_score, 4),
            mission_proximity_score=round(mission_score, 4),
            asset_criticality_score=round(asset_score, 4),
            component_criticality_score=round(comp_score, 4),
            safety_score=round(safety_score, 4),
            overdue_score=round(overdue_score, 4),
            total=total,
        )

        urgency = self._urgency_level(total, item.safety_classification)
        action = self._recommended_action(item, urgency)

        return PrioritizedItem(
            item_id=item.item_id,
            asset_id=item.asset_id,
            asset_code=item.asset_code,
            component_code=item.component_code,
            description=item.description,
            priority_score=total,
            urgency_level=urgency,
            blocks_mission=item.blocks_mission,
            score_breakdown=breakdown,
            contributing_factors=factors,
            recommended_action=action,
        )

    # ------------------------------------------------------------------
    # Sub-score helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _failure_risk_score(item: MaintenanceItem) -> float:
        if item.failure_probability is not None:
            return item.failure_probability
        if item.anomaly_score is not None:
            return 0.5 * item.anomaly_score
        return 0.25  # conservative default when no data

    @staticmethod
    def _rul_score(item: MaintenanceItem) -> float:
        if item.rul_hours is None:
            return 0.50 if item.hours_until_next_mission is not None else 0.25
        if item.rul_hours <= 0:
            return 1.0
        return max(0.0, 1.0 - item.rul_hours / 200.0)

    @staticmethod
    def _mission_proximity_score(item: MaintenanceItem) -> float:
        if item.hours_until_next_mission is None:
            return 0.0
        if item.blocks_mission and item.hours_until_next_mission < item.estimated_downtime_hours:
            return 1.0
        return max(0.0, min(1.0, 1.0 - item.hours_until_next_mission / 200.0))

    # ------------------------------------------------------------------
    # Urgency classification
    # ------------------------------------------------------------------

    @staticmethod
    def _urgency_level(score: float, safety: SafetyClassification) -> UrgencyLevel:
        # Safety override (always wins)
        if safety == SafetyClassification.AIRWORTHINESS_LIMITING:
            return UrgencyLevel.IMMEDIATE
        if safety == SafetyClassification.SAFETY_OF_FLIGHT and score >= 0.40:
            return UrgencyLevel.URGENT

        if score >= 0.80:
            return UrgencyLevel.IMMEDIATE
        if score >= 0.60:
            return UrgencyLevel.URGENT
        if score >= 0.40:
            return UrgencyLevel.SCHEDULED
        if score >= 0.20:
            return UrgencyLevel.ROUTINE
        return UrgencyLevel.DEFERRED

    # ------------------------------------------------------------------
    # Recommendation builder
    # ------------------------------------------------------------------

    @staticmethod
    def _recommended_action(item: MaintenanceItem, urgency: UrgencyLevel) -> str:
        if urgency == UrgencyLevel.IMMEDIATE:
            return (
                f"IMMEDIATE action required on {item.asset_code} / {item.component_code}. "
                f"Ground asset and schedule maintenance now. "
                f"Estimated downtime: {item.estimated_downtime_hours:.0f} h."
            )
        if urgency == UrgencyLevel.URGENT:
            return (
                f"Address {item.asset_code} / {item.component_code} within 72 h. "
                f"Do not assign to high-risk missions until resolved."
            )
        if urgency == UrgencyLevel.SCHEDULED:
            return (
                f"Schedule {item.asset_code} / {item.component_code} in next "
                f"maintenance window."
            )
        if urgency == UrgencyLevel.ROUTINE:
            return (
                f"Include {item.asset_code} / {item.component_code} in routine "
                f"maintenance at next convenient opportunity."
            )
        return (
            f"Defer {item.asset_code} / {item.component_code} to future scheduled "
            f"maintenance; no immediate risk identified."
        )
