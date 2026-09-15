"""
FleetSimulator — main simulation orchestrator.

Runs the causal chain for every asset, every component, every sensor,
at every timestep, producing the full fleet dataset.

Causal chain per timestep per component:
  1. Determine operating condition (environment.py)
  2. Check maintenance trigger → start maintenance if due
  3. Apply degradation step (degradation.py) OR maintenance health recovery
  4. Record truth (health, true_rul) in TruthLayer
  5. For each sensor: compute ideal signal → noise → fault → observed value
  6. Emit telemetry row (observable only, no health columns)
  7. Emit data quality event if fault was active
  8. Check failure condition → record failure event in truth; update asset status

Anti-leakage: the simulation loop writes to two separate structures:
  - _obs_rows  → telemetry, maintenance_events, dq_events (ML-visible)
  - fleet_truth → health trajectories, failure timestamps (labels only)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from app.ml.simulator.assembly import (
    AssetEntity,
    assemble_fleet,
    build_fleet_truth,
)
from app.ml.simulator.config import SimulatorConfig
from app.ml.simulator.degradation import (
    DegradationArchetype,
    assign_archetype,
    compute_true_rul,
    is_failed,
    step_health,
)
from app.ml.simulator.edge_cases import EdgeCaseInjectionPlan, EdgeCaseTag, EdgeCasePlanner
from app.ml.simulator.environment import (
    OperatingCondition,
    build_condition_schedule,
    condition_multiplier,
)
from app.ml.simulator.export import SimulationResult, build_result
from app.ml.simulator.maintenance import (
    should_trigger_maintenance,
    start_maintenance,
    step_maintenance,
)
from app.ml.simulator.mission import schedule_mission
from app.ml.simulator.rng import RNGManager
from app.ml.simulator.sensor import (
    ActiveFault,
    SensorFaultType,
    observe,
)
from app.ml.simulator.truth import ComponentTruth, FleetTruth


class FleetSimulator:
    """Simulates a synthetic fleet of assets from commission to end of observation.

    Usage
    -----
    cfg = load_profile("tiny")
    sim = FleetSimulator(cfg)
    result = sim.run()
    """

    def __init__(self, cfg: SimulatorConfig) -> None:
        self._cfg = cfg

    def run(self) -> SimulationResult:
        """Execute the full simulation and return a SimulationResult."""
        cfg = self._cfg
        profile = cfg.profile

        sim_start = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        n_steps = int(profile.sim_days * 24 / profile.timestep_hours)

        # --- Assemble fleet ------------------------------------------------
        assets, rng = assemble_fleet(cfg, sim_start)
        fleet_truth = build_fleet_truth(assets, cfg)

        # --- Build edge case injection plan --------------------------------
        sensor_map: dict[str, list[str]] = {
            a.asset_id: [s.sensor_id for c in a.components for s in c.sensors]
            for a in assets
        }
        component_map: dict[str, list[str]] = {
            a.asset_id: [c.component_id for c in a.components]
            for a in assets
        }
        planner = EdgeCasePlanner(
            params=cfg.edge_cases,
            asset_ids=[a.asset_id for a in assets],
            sensor_map=sensor_map,
            component_map=component_map,
            rng_manager=rng,
        )
        plan = planner.build()

        # Resolve health_dip_step (-1 → 25% into sim)
        for key in plan.health_dip_components:
            if plan.health_dip_step.get(key, -1) == -1:
                plan.health_dip_step[key] = int(n_steps * 0.25)

        # --- Pre-build condition schedules per asset -----------------------
        condition_schedules = {}
        for asset in assets:
            a_rng = rng.child("condition", asset.asset_id)
            condition_schedules[asset.asset_id] = build_condition_schedule(
                n_steps, profile.timestep_hours, a_rng, asset.usage_intensity
            )

        # --- Apply sensor fault plan to SensorState -----------------------
        _apply_sensor_fault_plan(plan, assets, rng, n_steps)

        # --- Insufficient data: mark assets that should stop early ---------
        insufficient_stop: dict[str, int] = {}
        for asset_id in plan.insufficient_data_assets:
            rng_i = rng.edge_case("insuf_step")
            insufficient_stop[asset_id] = int(rng_i.integers(
                2, cfg.edge_cases.insufficient_data_max_steps + 1
            ))

        # --- Observable row accumulators ----------------------------------
        tel_rows: list[dict] = []
        dq_rows: list[dict] = []
        maint_rows: list[dict] = []
        mission_rows: list[dict] = []
        asset_rows: list[dict] = []

        # --- Main simulation loop ----------------------------------------
        for asset in assets:
            self._simulate_asset(
                asset=asset,
                fleet_truth=fleet_truth,
                plan=plan,
                condition_schedule=condition_schedules[asset.asset_id],
                rng=rng,
                cfg=cfg,
                sim_start=sim_start,
                n_steps=n_steps,
                insufficient_stop=insufficient_stop,
                tel_rows=tel_rows,
                dq_rows=dq_rows,
                maint_rows=maint_rows,
                mission_rows=mission_rows,
            )

        # --- Asset summary rows -------------------------------------------
        for asset in assets:
            at = fleet_truth.asset_truths[asset.asset_id]
            asset_rows.append({
                "asset_id": asset.asset_id,
                "asset_code": asset.asset_code,
                "asset_type": asset.asset_type,
                "commission_date": asset.commission_date.date().isoformat(),
                "total_hours": asset.total_hours,
                "is_active": not asset.is_failed,
                "usage_intensity": asset.usage_intensity,
                "sensor_quality": asset.sensor_quality,
            })

        # --- Component and sensor summary rows ----------------------------
        comp_rows: list[dict] = []
        sensor_rows: list[dict] = []
        for asset in assets:
            for comp in asset.components:
                comp_rows.append({
                    "component_id": comp.component_id,
                    "asset_id": asset.asset_id,
                    "component_code": f"{comp.spec.component_type}-{comp.component_id[:8]}",
                    "component_type": comp.spec.component_type,
                    "name": comp.spec.name_template,
                    "mtbf_hours": comp.maintenance_state.mtbf_hours,
                    "is_active": True,
                    "archetype": comp.archetype.value,
                })
                for sensor in comp.sensors:
                    sensor_rows.append({
                        "sensor_id": sensor.sensor_id,
                        "component_id": comp.component_id,
                        "asset_id": asset.asset_id,
                        "sensor_code": f"{sensor.spec.sensor_type}-{sensor.sensor_id[:8]}",
                        "sensor_type": sensor.spec.sensor_type,
                        "unit": sensor.spec.unit,
                        "nominal_min": sensor.spec.nominal_min,
                        "nominal_max": sensor.spec.nominal_max,
                        "critical_min": sensor.spec.critical_min,
                        "critical_max": sensor.spec.critical_max,
                        "is_active": True,
                    })

        return build_result(
            asset_rows=asset_rows,
            component_rows=comp_rows,
            sensor_rows=sensor_rows,
            telemetry_rows=tel_rows,
            dq_rows=dq_rows,
            maintenance_rows=maint_rows,
            mission_rows=mission_rows,
            fleet_truth=fleet_truth,
            plan=plan,
            cfg=cfg,
        )

    # ------------------------------------------------------------------
    # Per-asset simulation
    # ------------------------------------------------------------------

    def _simulate_asset(
        self,
        asset: AssetEntity,
        fleet_truth: FleetTruth,
        plan: EdgeCaseInjectionPlan,
        condition_schedule: Any,
        rng: RNGManager,
        cfg: SimulatorConfig,
        sim_start: datetime,
        n_steps: int,
        insufficient_stop: dict[str, int],
        tel_rows: list[dict],
        dq_rows: list[dict],
        maint_rows: list[dict],
        mission_rows: list[dict],
    ) -> None:
        """Run the full simulation for one asset."""
        dt = cfg.profile.timestep_hours
        max_step = insufficient_stop.get(asset.asset_id, n_steps)
        tags = plan.asset_tags.get(asset.asset_id, set())

        # Overdue maintenance: suppress scheduled maintenance check for this asset
        is_overdue_asset = asset.asset_id in plan.overdue_maintenance_assets

        # Mission conflict scheduling
        needs_conflict_mission = asset.asset_id in plan.mission_conflict_assets

        last_mission_step = -9999

        for step in range(max_step):
            ts = sim_start + timedelta(hours=step * dt)
            condition = condition_schedule[step]

            # Maintenance forces MAINTENANCE_GROUND condition
            any_maint_active = any(
                c.maintenance_state.maintenance_active for c in asset.components
            )
            if any_maint_active:
                condition = OperatingCondition.MAINTENANCE_GROUND

            asset.total_hours += dt

            for comp in asset.components:
                if asset.is_failed:
                    break

                comp_truth = fleet_truth.asset_truths[asset.asset_id].component_truths[
                    comp.component_id
                ]

                cond_mult = condition_multiplier(condition, cfg.degradation)

                # --- Health dip edge case (temporary anomaly, then recovery) ---
                dip_key = (asset.asset_id, comp.component_id)
                if dip_key in plan.health_dip_components:
                    dip_step = plan.health_dip_step.get(dip_key, -1)
                    if dip_step != -1:
                        if step == dip_step:
                            # Impose a temporary dip
                            comp.health = max(0.20, comp.health - 0.35)
                        elif step == dip_step + 15:
                            # Partial recovery (component didn't actually fail)
                            comp.health = min(1.0, comp.health + 0.25)

                # --- Maintenance trigger (skip for overdue asset on scheduled) ---
                if is_overdue_asset:
                    do_corrective_only = comp.health <= cfg.maintenance.corrective_trigger_health
                    should_maint = do_corrective_only
                else:
                    should_maint = should_trigger_maintenance(
                        comp.maintenance_state, comp.health, cfg.maintenance
                    )

                if should_maint:
                    comp_rng = rng.child("maintenance", comp.component_id)
                    event, target_health = start_maintenance(
                        comp.maintenance_state,
                        asset.asset_id,
                        comp.component_id,
                        ts,
                        asset.total_hours,
                        comp.health,
                        cfg.maintenance,
                        comp_rng,
                    )
                    maint_rows.append({
                        "event_id": event.event_id,
                        "asset_id": event.asset_id,
                        "component_id": event.component_id,
                        "event_type": event.event_type,
                        "performed_at": ts.isoformat(),
                        "asset_hours_at_event": event.asset_hours_at_event,
                        "description": event.description,
                    })
                    comp_truth.maintenance_timestamps.append(ts)

                # --- Advance maintenance state / degrade ---
                new_health, maint_completed = step_maintenance(
                    comp.maintenance_state, comp.health, dt
                )

                if not comp.maintenance_state.maintenance_active and not (
                    comp.maintenance_state.recovery_steps_remaining > 0
                ):
                    # Normal degradation
                    comp_rng = rng.child("degrade", comp.component_id)
                    new_health = step_health(
                        comp.archetype,
                        new_health,
                        dt,
                        cond_mult,
                        cfg.degradation,
                        comp_rng,
                        comp.degradation_multiplier,
                    )

                comp.health = new_health

                # --- Record truth ---
                comp_truth.timestamps.append(ts)
                comp_truth.health.append(comp.health)

                # --- Check failure ---
                if is_failed(comp.health) and comp_truth.failure_timestamp is None:
                    comp_truth.failure_timestamp = ts
                    comp_truth.failure_type = "DEGRADATION_FAILURE"
                    asset.is_failed = True

                # --- Sensor observations ---
                for sensor_entity in comp.sensors:
                    s_rng = rng.child("sensor", sensor_entity.sensor_id)
                    value, is_dup, fault_type = observe(
                        sensor_entity.state,
                        comp.health,
                        condition,
                        s_rng,
                    )

                    if value is not None:
                        row = {
                            "asset_id": asset.asset_id,
                            "sensor_id": sensor_entity.sensor_id,
                            "component_id": comp.component_id,
                            "value": float(value),
                            "recorded_at": ts.isoformat(),
                            "operating_hours": asset.total_hours,
                            "operating_condition": condition.value,
                            "source": "simulator",
                        }
                        tel_rows.append(row)
                        if is_dup:
                            tel_rows.append(row.copy())

                    # Emit data quality event if fault active
                    if fault_type != SensorFaultType.NONE:
                        import hashlib as _hl
                        _k = f"{sensor_entity.sensor_id}:{step}:{fault_type.value}"
                        _h = _hl.sha256(_k.encode()).hexdigest()
                        _eid = f"{_h[:8]}-{_h[8:12]}-{_h[12:16]}-{_h[16:20]}-{_h[20:32]}"
                        dq_rows.append({
                            "event_id": _eid,
                            "asset_id": asset.asset_id,
                            "sensor_id": sensor_entity.sensor_id,
                            "event_type": fault_type.value,
                            "severity": _fault_severity(fault_type),
                            "description": f"Sensor fault: {fault_type.value}",
                            "started_at": ts.isoformat(),
                            "is_active": True,
                        })

            # --- Mission scheduling (occasional) ---
            if step - last_mission_step > int(cfg.missions.mission_interval_days_min * 24 / dt):
                # Compute approximate true RUL from last known health for conflict check
                comp_truths = list(
                    fleet_truth.asset_truths[asset.asset_id].component_truths.values()
                )
                min_health = min((ct.health[-1] for ct in comp_truths if ct.health), default=1.0)
                # Approximate RUL: assume linear at gradual rate
                approx_rul = min_health / cfg.degradation.gradual_rate if min_health > 0.05 else 0.0

                force_conflict = (
                    needs_conflict_mission and step > int(n_steps * 0.10)
                )
                mission_rng = rng.child("mission", asset.asset_id, str(step))
                mission = schedule_mission(
                    asset.mission_state,
                    asset.asset_id,
                    asset.asset_type,
                    ts,
                    min_health,
                    approx_rul,
                    cfg.missions,
                    mission_rng,
                    force_conflict=force_conflict,
                )
                if mission:
                    mission_rows.append({
                        "mission_id": mission.mission_id,
                        "mission_code": mission.mission_code,
                        "asset_id": mission.asset_id,
                        "name": mission.name,
                        "criticality": mission.criticality,
                        "scheduled_start": mission.scheduled_start.isoformat(),
                        "duration_hours": mission.duration_hours,
                        "status": mission.status,
                        "role": mission.role,
                        "is_conflict": mission.is_conflict,
                    })
                    last_mission_step = step
                    if force_conflict:
                        needs_conflict_mission = False

        # --- Compute true RUL for all components ---
        for comp in asset.components:
            comp_truth = fleet_truth.asset_truths[asset.asset_id].component_truths[
                comp.component_id
            ]
            comp_truth.true_rul = compute_true_rul(comp_truth.health, dt)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _fault_severity(fault_type: SensorFaultType) -> str:
    if fault_type in (SensorFaultType.SENSOR_FAILURE, SensorFaultType.STUCK):
        return "HIGH"
    if fault_type in (SensorFaultType.OUTLIER, SensorFaultType.DRIFT):
        return "MEDIUM"
    return "LOW"


def _apply_sensor_fault_plan(
    plan: EdgeCaseInjectionPlan,
    assets: list[AssetEntity],
    rng: RNGManager,
    n_steps: int,
) -> None:
    """Apply the EdgeCaseInjectionPlan's sensor faults to SensorState objects."""
    sensor_index: dict[str, Any] = {}  # sensor_id → SensorEntity
    for asset in assets:
        for comp in asset.components:
            for sensor_entity in comp.sensors:
                sensor_index[sensor_entity.sensor_id] = sensor_entity

    for (asset_id, sensor_id), fault_cfg in plan.sensor_faults.items():
        if sensor_id not in sensor_index:
            continue
        sensor_entity = sensor_index[sensor_id]
        state = sensor_entity.state
        fault_type_str = fault_cfg["fault_type"]

        try:
            ft = SensorFaultType(fault_type_str)
        except ValueError:
            continue

        duration = fault_cfg.get("duration_steps", n_steps)
        drift_rate = fault_cfg.get("drift_rate", 0.0)

        if ft == SensorFaultType.MISSING:
            # Mark as MISSING for the configured fraction of steps.
            # We implement this by setting the fault with n_steps duration
            # and letting the engine handle the fraction via probability.
            # For simplicity, we set a MISSING fault for duration = n_steps
            # and rely on sensor state logic. The actual missing_fraction
            # is enforced in the observe() step via per-step probability.
            state.active_fault = ActiveFault(
                fault_type=SensorFaultType.MISSING,
                remaining_steps=int(n_steps * fault_cfg.get("missing_fraction", 0.4)),
            )
        elif ft == SensorFaultType.STALE:
            state.active_fault = ActiveFault(
                fault_type=SensorFaultType.STALE,
                remaining_steps=duration,
            )
        elif ft == SensorFaultType.STUCK:
            state.active_fault = ActiveFault(
                fault_type=SensorFaultType.STUCK,
                remaining_steps=duration,
            )
        elif ft == SensorFaultType.OUTLIER:
            state.active_fault = ActiveFault(
                fault_type=SensorFaultType.OUTLIER,
                remaining_steps=1,
            )
        elif ft == SensorFaultType.DRIFT:
            state.active_fault = ActiveFault(
                fault_type=SensorFaultType.DRIFT,
                remaining_steps=duration,
                drift_rate=drift_rate,
            )
        elif ft == SensorFaultType.DUPLICATE:
            state.active_fault = ActiveFault(
                fault_type=SensorFaultType.DUPLICATE,
                remaining_steps=1,
            )
            state.duplicate_pending = True
        elif ft == SensorFaultType.SENSOR_FAILURE:
            state.active_fault = ActiveFault(
                fault_type=SensorFaultType.SENSOR_FAILURE,
                remaining_steps=duration,
            )
