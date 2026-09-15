"""
MissionEngine — deterministic mission readiness aggregation.

Algorithm overview
------------------
1. For each capability requirement:
   a. Count assigned assets in each readiness state (READY/AT_RISK/NOT_READY/UNKNOWN).
   b. Determine if the requirement is FULLY_MET, PARTIALLY_MET, or UNMET.
   c. For gaps, search fleet for substitute candidates and rank them.

2. Detect scheduling conflicts:
   - Asset assigned to more than one mission in the same window.
   - Asset is NOT_READY or under maintenance but still assigned.

3. Compute risk score:
   - Base = 0.0
   - +0.40 per critical capability gap (capped)
   - +0.20 per non-critical capability gap (capped)
   - +0.10 per AT_RISK assigned asset per critical capability
   - +0.15 per UNKNOWN assigned asset per critical capability
   - +0.05 per scheduling conflict
   - Clamped to [0.0, 1.0]

4. Determine mission status:
   NO_GO       — any critical gap, or risk_score >= critical_threshold (0.70)
   GO_WITH_RISK — no critical gaps but risk_score >= moderate_threshold (0.30)
   GO          — all requirements met, risk_score < moderate_threshold
   UNKNOWN     — any required capability has zero assessed assets

Risk → MissionRiskLevel mapping:
   [0.00, 0.30) → LOW
   [0.30, 0.55) → MODERATE
   [0.55, 0.70) → HIGH
   [0.70, 1.00] → CRITICAL

Substitution scoring (higher is better):
   base = 1.0
   - READY:   +0.40
   - AT_RISK: +0.10
   - confidence weight: × confidence
   - bonus if already in fleet: no change (no special treatment)
   Candidates are sorted descending by suitability_score.
"""

from __future__ import annotations

from datetime import datetime

from app.ml.mission.models import (
    AssetCapability,
    CapabilityReadiness,
    CapabilityRequirement,
    ConflictReport,
    MissionInput,
    MissionOutput,
    MissionRiskLevel,
    MissionStatus,
    ReadinessGap,
    SubstitutionCandidate,
)

_READY = "READY"
_AT_RISK = "AT_RISK"
_NOT_READY = "NOT_READY"
_UNKNOWN = "UNKNOWN"


class MissionEngine:
    """Deterministic mission readiness engine.

    Usage::

        engine = MissionEngine()
        result = engine.evaluate(mission_input)
    """

    # Risk thresholds
    _CRITICAL_RISK_THRESHOLD: float = 0.70
    _MODERATE_RISK_THRESHOLD: float = 0.30

    def evaluate(self, inp: MissionInput) -> MissionOutput:
        """Evaluate readiness for a single mission.

        Args:
            inp: MissionInput with requirements, assigned assets, and fleet.

        Returns:
            MissionOutput with status, risk, gaps, substitutions, and conflicts.
        """
        factors: list[tuple[str, str]] = []

        # ----------------------------------------------------------------
        # Step 1: Per-capability readiness breakdown
        # ----------------------------------------------------------------
        cap_readiness: list[CapabilityReadiness] = []
        gaps: list[ReadinessGap] = []
        has_unknown_cap = False

        for req in inp.requirements:
            cr = self._assess_capability(req, inp.assigned_assets)
            cap_readiness.append(cr)

            if not cr.ready_assets and not cr.at_risk_assets and not cr.not_ready_assets and not cr.unknown_assets:
                # No assigned assets at all for this capability
                has_unknown_cap = True
                gap = ReadinessGap(
                    capability=req.capability,
                    required_count=req.required_count,
                    available_count=0,
                    at_risk_count=0,
                    is_critical=req.is_critical,
                    substitutions=self._find_substitutions(
                        req.capability, req.required_count, inp.assigned_assets, inp.fleet_assets
                    ),
                )
                gaps.append(gap)
                factors.append((
                    "NO_ASSETS_ASSIGNED",
                    f"No assets assigned for capability '{req.capability}'.",
                ))
            elif not cr.ready_assets and cr.unknown_assets and not cr.at_risk_assets:
                # All assigned assets are UNKNOWN — cannot assess
                has_unknown_cap = True

            ready_count = len(cr.ready_assets)
            if ready_count < req.required_count:
                gap = ReadinessGap(
                    capability=req.capability,
                    required_count=req.required_count,
                    available_count=ready_count,
                    at_risk_count=len(cr.at_risk_assets),
                    is_critical=req.is_critical,
                    substitutions=self._find_substitutions(
                        req.capability, req.required_count - ready_count,
                        inp.assigned_assets, inp.fleet_assets,
                    ),
                )
                # Avoid duplicate gap entries
                if not any(g.capability == req.capability for g in gaps):
                    gaps.append(gap)
                    if req.is_critical:
                        factors.append((
                            "CRITICAL_CAPABILITY_GAP",
                            f"Critical capability '{req.capability}': "
                            f"need {req.required_count}, have {ready_count} READY.",
                        ))
                    else:
                        factors.append((
                            "CAPABILITY_GAP",
                            f"Non-critical capability '{req.capability}': "
                            f"need {req.required_count}, have {ready_count} READY.",
                        ))

        # ----------------------------------------------------------------
        # Step 2: Detect scheduling conflicts
        # ----------------------------------------------------------------
        conflicts = self._detect_conflicts(inp)
        for c in conflicts:
            factors.append(("SCHEDULING_CONFLICT", c.description))

        # ----------------------------------------------------------------
        # Step 3: Compute risk score
        # ----------------------------------------------------------------
        risk_score = self._compute_risk(inp.requirements, gaps, cap_readiness, conflicts)

        # ----------------------------------------------------------------
        # Step 4: Determine mission status
        # ----------------------------------------------------------------
        has_critical_gap = any(g.is_critical and g.shortage > 0 for g in gaps)

        if has_unknown_cap and not has_critical_gap and not gaps:
            status = MissionStatus.UNKNOWN
        elif has_critical_gap or risk_score >= self._CRITICAL_RISK_THRESHOLD:
            status = MissionStatus.NO_GO
        elif risk_score >= self._MODERATE_RISK_THRESHOLD:
            status = MissionStatus.GO_WITH_RISK
        else:
            status = MissionStatus.GO

        # ----------------------------------------------------------------
        # Step 5: Map risk score to risk level
        # ----------------------------------------------------------------
        risk_level = self._risk_level(risk_score)

        # ----------------------------------------------------------------
        # Step 6: Build summary
        # ----------------------------------------------------------------
        summary = self._build_summary(inp, status, risk_level, gaps, conflicts)

        return MissionOutput(
            mission_id=inp.mission_id,
            mission_code=inp.mission_code,
            status=status,
            risk_level=risk_level,
            risk_score=round(risk_score, 4),
            capability_readiness=cap_readiness,
            gaps=gaps,
            conflicts=conflicts,
            evaluated_at=inp.evaluated_at,
            summary=summary,
            contributing_factors=factors,
        )

    # ------------------------------------------------------------------
    # Private: capability assessment
    # ------------------------------------------------------------------

    @staticmethod
    def _assess_capability(
        req: CapabilityRequirement,
        assets: list[AssetCapability],
    ) -> CapabilityReadiness:
        """Return per-state asset lists for one capability requirement."""
        ready: list[str] = []
        at_risk: list[str] = []
        not_ready: list[str] = []
        unknown: list[str] = []

        for asset in assets:
            if req.capability not in asset.capabilities:
                continue
            s = asset.readiness_status
            if s == _READY:
                ready.append(asset.asset_code)
            elif s == _AT_RISK:
                at_risk.append(asset.asset_code)
            elif s == _NOT_READY:
                not_ready.append(asset.asset_code)
            else:
                unknown.append(asset.asset_code)

        return CapabilityReadiness(
            capability=req.capability,
            required_count=req.required_count,
            ready_assets=ready,
            at_risk_assets=at_risk,
            not_ready_assets=not_ready,
            unknown_assets=unknown,
        )

    # ------------------------------------------------------------------
    # Private: substitution search
    # ------------------------------------------------------------------

    def _find_substitutions(
        self,
        capability: str,
        needed: int,
        assigned: list[AssetCapability],
        fleet: list[AssetCapability],
    ) -> list[SubstitutionCandidate]:
        """Find and rank substitute candidates from the fleet.

        Excludes assets already assigned to this mission.
        Includes READY and AT_RISK candidates only.
        Returns up to (needed * 3) candidates, ranked by suitability.
        """
        assigned_ids = {a.asset_id for a in assigned}
        candidates: list[SubstitutionCandidate] = []

        for asset in fleet:
            if asset.asset_id in assigned_ids:
                continue
            if capability not in asset.capabilities:
                continue
            if asset.readiness_status not in (_READY, _AT_RISK):
                continue

            score = self._suitability_score(asset)
            reason = (
                f"Asset {asset.asset_code} is {asset.readiness_status} "
                f"with confidence {asset.readiness_confidence:.0%}."
            )
            candidates.append(SubstitutionCandidate(
                asset_id=asset.asset_id,
                asset_code=asset.asset_code,
                capability=capability,
                readiness_status=asset.readiness_status,
                confidence=asset.readiness_confidence,
                suitability_score=round(score, 4),
                reason=reason,
            ))

        # Sort by suitability descending
        candidates.sort(key=lambda c: c.suitability_score, reverse=True)
        return candidates[: needed * 3]

    @staticmethod
    def _suitability_score(asset: AssetCapability) -> float:
        """Numeric suitability for substitution (higher = better)."""
        base = 0.0
        if asset.readiness_status == _READY:
            base = 0.60
        elif asset.readiness_status == _AT_RISK:
            base = 0.30
        # Weight by confidence
        return base * asset.readiness_confidence

    # ------------------------------------------------------------------
    # Private: conflict detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_conflicts(inp: MissionInput) -> list[ConflictReport]:
        """Detect scheduling conflicts among assigned assets."""
        conflicts: list[ConflictReport] = []

        for asset in inp.assigned_assets:
            # Double-assignment: asset is assigned to another mission
            if len(asset.assigned_mission_ids) > 1 or (
                asset.assigned_mission_ids
                and asset.assigned_mission_ids[0] != inp.mission_id
            ):
                other = [m for m in asset.assigned_mission_ids if m != inp.mission_id]
                if other:
                    conflicts.append(ConflictReport(
                        asset_id=asset.asset_id,
                        asset_code=asset.asset_code,
                        conflicting_mission_ids=[inp.mission_id] + other,
                        conflict_type="DOUBLE_ASSIGNED",
                        description=(
                            f"Asset {asset.asset_code} is assigned to both "
                            f"mission {inp.mission_id} and {', '.join(other)}."
                        ),
                    ))

            # Asset is NOT_READY but still assigned
            if asset.readiness_status == _NOT_READY:
                conflicts.append(ConflictReport(
                    asset_id=asset.asset_id,
                    asset_code=asset.asset_code,
                    conflicting_mission_ids=[inp.mission_id],
                    conflict_type="UNAVAILABLE",
                    description=(
                        f"Asset {asset.asset_code} is NOT_READY "
                        f"({asset.primary_reason}) but is assigned to mission "
                        f"{inp.mission_id}."
                    ),
                ))

        return conflicts

    # ------------------------------------------------------------------
    # Private: risk computation
    # ------------------------------------------------------------------

    def _compute_risk(
        self,
        requirements: list[CapabilityRequirement],
        gaps: list[ReadinessGap],
        cap_readiness: list[CapabilityReadiness],
        conflicts: list[ConflictReport],
    ) -> float:
        risk = 0.0

        for gap in gaps:
            if gap.is_critical:
                risk += 0.40 * min(gap.shortage, 3)  # cap at 3 shortages
            else:
                risk += 0.20 * min(gap.shortage, 2)

        # AT_RISK and UNKNOWN assets in critical capabilities add risk
        req_by_cap = {r.capability: r for r in requirements}
        for cr in cap_readiness:
            req = req_by_cap.get(cr.capability)
            if req and req.is_critical:
                risk += 0.10 * len(cr.at_risk_assets)
                risk += 0.15 * len(cr.unknown_assets)

        # Conflicts
        risk += 0.05 * len(conflicts)

        return min(1.0, max(0.0, risk))

    @staticmethod
    def _risk_level(risk_score: float) -> MissionRiskLevel:
        if risk_score < 0.30:
            return MissionRiskLevel.LOW
        if risk_score < 0.55:
            return MissionRiskLevel.MODERATE
        if risk_score < 0.70:
            return MissionRiskLevel.HIGH
        return MissionRiskLevel.CRITICAL

    # ------------------------------------------------------------------
    # Private: summary builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(
        inp: MissionInput,
        status: MissionStatus,
        risk_level: MissionRiskLevel,
        gaps: list[ReadinessGap],
        conflicts: list[ConflictReport],
    ) -> str:
        total_assigned = len(inp.assigned_assets)
        critical_gaps = [g for g in gaps if g.is_critical and g.shortage > 0]
        parts = [
            f"Mission {inp.mission_code}: {status.value} ({risk_level.value} risk). "
            f"{total_assigned} asset(s) assigned, "
            f"{len(gaps)} capability gap(s), "
            f"{len(critical_gaps)} critical gap(s), "
            f"{len(conflicts)} conflict(s)."
        ]
        if critical_gaps:
            names = ", ".join(g.capability for g in critical_gaps)
            parts.append(f"Critical gaps: {names}.")
        return " ".join(parts)
