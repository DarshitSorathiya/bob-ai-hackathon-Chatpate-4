"""
Fleet assembly — asset, component, and sensor factory.

Builds the entity graph (assets → components → sensors) from the
SimulatorConfig, assigning unique IDs and initialising all mutable
runtime state objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from app.ml.simulator.config import AssetTypeSpec, ComponentSpec, SensorSpec, SimulatorConfig
from app.ml.simulator.degradation import DegradationArchetype, assign_archetype
from app.ml.simulator.maintenance import ComponentMaintenanceState
from app.ml.simulator.mission import AssetMissionState
from app.ml.simulator.rng import RNGManager
from app.ml.simulator.sensor import SensorState
from app.ml.simulator.truth import AssetTruth, ComponentTruth, FleetTruth


def _make_uuid(rng: np.random.Generator) -> str:
    """Generate a deterministic UUID-format string from an RNG."""
    raw = rng.integers(0, 256, size=16, dtype=np.uint8)
    # Set UUID version 4 bits
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    h = raw.tobytes().hex()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


# ─── Runtime entities ─────────────────────────────────────────────────────────


@dataclass
class SensorEntity:
    sensor_id: str
    component_id: str
    asset_id: str
    spec: SensorSpec
    state: SensorState


@dataclass
class ComponentEntity:
    component_id: str
    asset_id: str
    spec: ComponentSpec
    archetype: DegradationArchetype
    degradation_multiplier: float
    maintenance_state: ComponentMaintenanceState
    sensors: list[SensorEntity] = field(default_factory=list)
    health: float = 1.0    # current latent health


@dataclass
class AssetEntity:
    asset_id: str
    asset_code: str
    asset_type: str
    commission_date: datetime
    usage_intensity: float
    sensor_quality: float
    components: list[ComponentEntity] = field(default_factory=list)
    mission_state: AssetMissionState = field(default_factory=lambda: AssetMissionState(asset_id=""))
    total_hours: float = 0.0
    is_failed: bool = False

    def __post_init__(self) -> None:
        if self.mission_state.asset_id == "":
            self.mission_state = AssetMissionState(asset_id=self.asset_id)


# ─── Fleet assembly ────────────────────────────────────────────────────────────


def _sample_asset_type(
    asset_types: list[AssetTypeSpec],
    rng: np.random.Generator,
) -> AssetTypeSpec:
    """Sample an asset type weighted by fleet_weight."""
    weights = np.array([at.fleet_weight for at in asset_types], dtype=float)
    weights /= weights.sum()
    idx = int(rng.choice(len(asset_types), p=weights))
    return asset_types[idx]


def _build_sensor(
    spec: SensorSpec,
    component_id: str,
    asset_id: str,
    sensor_idx: int,
    sensor_quality: float,
    rng: RNGManager,
) -> SensorEntity:
    id_rng = rng.child("sensor_id", component_id, spec.sensor_type, str(sensor_idx))
    sensor_id = _make_uuid(id_rng)
    # Adjust noise sigma by sensor quality (lower quality = more noise)
    adjusted_spec = SensorSpec(
        sensor_type=spec.sensor_type,
        unit=spec.unit,
        nominal_min=spec.nominal_min,
        nominal_max=spec.nominal_max,
        critical_min=spec.critical_min,
        critical_max=spec.critical_max,
        noise_sigma=spec.noise_sigma / sensor_quality,
        degradation_sensitivity=spec.degradation_sensitivity,
        degradation_direction=spec.degradation_direction,
    )
    state = SensorState(
        sensor_id=sensor_id,
        spec=adjusted_spec,
    )
    return SensorEntity(
        sensor_id=sensor_id,
        component_id=component_id,
        asset_id=asset_id,
        spec=adjusted_spec,
        state=state,
    )


def _build_component(
    spec: ComponentSpec,
    asset_id: str,
    comp_idx: int,
    degradation_multiplier: float,
    sensor_quality: float,
    forced_archetype: DegradationArchetype | None,
    rng: RNGManager,
    comp_rng: np.random.Generator,
) -> ComponentEntity:
    id_rng = rng.child("component_id", asset_id, spec.component_type, str(comp_idx))
    component_id = _make_uuid(id_rng)

    # Fleet heterogeneity on MTBF
    mtbf = float(np.clip(
        comp_rng.normal(spec.mtbf_hours, spec.mtbf_spread),
        spec.mtbf_hours * 0.5,
        spec.mtbf_hours * 2.0,
    ))

    archetype = forced_archetype if forced_archetype else assign_archetype(comp_rng, 1)

    maintenance_state = ComponentMaintenanceState(
        component_id=component_id,
        asset_id=asset_id,
        mtbf_hours=mtbf,
    )

    sensors = [
        _build_sensor(
            sspec,
            component_id,
            asset_id,
            sidx,
            sensor_quality,
            rng,
        )
        for sidx, sspec in enumerate(spec.sensors)
    ]

    return ComponentEntity(
        component_id=component_id,
        asset_id=asset_id,
        spec=spec,
        archetype=archetype,
        degradation_multiplier=degradation_multiplier,
        maintenance_state=maintenance_state,
        sensors=sensors,
    )


def _build_asset(
    asset_type_spec: AssetTypeSpec,
    asset_idx: int,
    asset_counters: dict[str, int],
    sim_start: datetime,
    forced_archetypes: dict[int, DegradationArchetype],  # comp_idx → archetype
    rng: RNGManager,
    asset_rng: np.random.Generator,
    cfg: SimulatorConfig,
) -> AssetEntity:
    atype = asset_type_spec.asset_type
    prefix = asset_type_spec.asset_code_prefix
    count = asset_counters.get(atype, 0) + 1
    asset_counters[atype] = count
    asset_code = f"{prefix}-{count:03d}"
    asset_id = _make_uuid(rng.child("asset_id", str(asset_idx)))

    # Fleet heterogeneity
    usage_intensity = float(np.clip(asset_rng.uniform(0.5, 1.5), 0.5, 1.5))
    sensor_quality = float(np.clip(asset_rng.uniform(0.7, 1.0), 0.7, 1.0))
    degradation_multiplier = float(np.clip(
        np.exp(asset_rng.normal(
            cfg.degradation.degradation_multiplier_mu,
            cfg.degradation.degradation_multiplier_sigma,
        )),
        0.3, 3.0,
    ))

    # Commission date: random offset in the past
    days_ago = int(asset_rng.uniform(30, 730))
    commission_date = datetime(
        sim_start.year, sim_start.month, sim_start.day, tzinfo=timezone.utc
    )

    components = []
    for cidx, comp_spec in enumerate(asset_type_spec.components):
        comp_rng = rng.child("component", asset_id, str(cidx))
        forced_arch = forced_archetypes.get(cidx)
        comp = _build_component(
            spec=comp_spec,
            asset_id=asset_id,
            comp_idx=cidx,
            degradation_multiplier=degradation_multiplier,
            sensor_quality=sensor_quality,
            forced_archetype=forced_arch,
            rng=rng,
            comp_rng=comp_rng,
        )
        components.append(comp)

    return AssetEntity(
        asset_id=asset_id,
        asset_code=asset_code,
        asset_type=atype,
        commission_date=commission_date,
        usage_intensity=usage_intensity,
        sensor_quality=sensor_quality,
        components=components,
    )


def assemble_fleet(
    cfg: SimulatorConfig,
    sim_start: datetime,
    forced_archetypes_by_asset: dict[int, dict[int, DegradationArchetype]] | None = None,
) -> tuple[list[AssetEntity], RNGManager]:
    """Build the complete fleet entity graph.

    Parameters
    ----------
    cfg:
        Simulator configuration.
    sim_start:
        Simulation start timestamp.
    forced_archetypes_by_asset:
        Optional map: asset_idx → {comp_idx → archetype} for edge case injection.

    Returns
    -------
    (assets, rng_manager)
    """
    rng = RNGManager(cfg.profile.seed)
    fleet_rng = rng.fleet()

    asset_counters: dict[str, int] = {}
    assets: list[AssetEntity] = []

    for asset_idx in range(cfg.profile.n_assets):
        asset_type_spec = _sample_asset_type(cfg.asset_types, fleet_rng)
        asset_rng = rng.child("asset", str(asset_idx))

        forced = {}
        if forced_archetypes_by_asset and asset_idx in forced_archetypes_by_asset:
            forced = forced_archetypes_by_asset[asset_idx]

        asset = _build_asset(
            asset_type_spec=asset_type_spec,
            asset_idx=asset_idx,
            asset_counters=asset_counters,
            sim_start=sim_start,
            forced_archetypes=forced,
            rng=rng,
            asset_rng=asset_rng,
            cfg=cfg,
        )
        assets.append(asset)

    return assets, rng


def build_fleet_truth(assets: list[AssetEntity], cfg: SimulatorConfig) -> FleetTruth:
    """Initialise an empty FleetTruth from the assembled asset graph."""
    fleet_truth = FleetTruth(
        seed=cfg.profile.seed,
        n_assets=len(assets),
        sim_days=cfg.profile.sim_days,
        timestep_hours=cfg.profile.timestep_hours,
    )
    for asset in assets:
        asset_truth = AssetTruth(
            asset_id=asset.asset_id,
            asset_code=asset.asset_code,
            asset_type=asset.asset_type,
            usage_intensity=asset.usage_intensity,
            sensor_quality=asset.sensor_quality,
        )
        for comp in asset.components:
            comp_truth = ComponentTruth(
                component_id=comp.component_id,
                asset_id=asset.asset_id,
                component_type=comp.spec.component_type,
                archetype=comp.archetype.value,
                degradation_multiplier=comp.degradation_multiplier,
            )
            asset_truth.component_truths[comp.component_id] = comp_truth
        fleet_truth.asset_truths[asset.asset_id] = asset_truth

    return fleet_truth
