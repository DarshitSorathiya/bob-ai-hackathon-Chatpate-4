"""
Simulator configuration — data-classes and YAML profile loader.

All simulator behaviour is driven by a SimulatorConfig. The config fully
determines output given a fixed seed, making every run reproducible.

Profile hierarchy
-----------------
  SimulatorConfig
    └─ FleetProfile          (scale: n_assets, sim_days, seed)
    └─ List[AssetTypeSpec]   (which asset types and their weights)
        └─ List[ComponentSpec]
            └─ List[SensorSpec]
    └─ DegradationParams
    └─ MaintenanceParams
    └─ MissionParams
    └─ EdgeCaseParams
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ─── Paths ────────────────────────────────────────────────────────────────────

PROFILES_DIR = Path(__file__).resolve().parents[3] / "data" / "simulator" / "profiles"

# ─── Leaf specs ───────────────────────────────────────────────────────────────


@dataclass
class SensorSpec:
    """Physical characteristics of one sensor type."""

    sensor_type: str          # e.g. "VIBRATION_RMS"
    unit: str                 # e.g. "mm/s"
    nominal_min: float        # healthy lower bound
    nominal_max: float        # healthy upper bound
    critical_min: float       # absolute lower safety limit
    critical_max: float       # absolute upper safety limit
    noise_sigma: float        # Gaussian noise std in nominal units
    # Signal response: how much the reading shifts per unit of health loss
    # (health ∈ [0,1]; 0 = completely degraded)
    degradation_sensitivity: float  # reading shift = sensitivity * (1 - health)
    degradation_direction: float    # +1 = rises as health falls, -1 = drops


@dataclass
class ComponentSpec:
    """Specification for one component type."""

    component_type: str         # e.g. "ENGINE_CORE"
    name_template: str          # e.g. "Engine Core {idx}"
    mtbf_hours: float           # mean time between failures (nominal)
    mtbf_spread: float          # std of MTBF across fleet (heterogeneity)
    sensors: list[SensorSpec] = field(default_factory=list)


@dataclass
class AssetTypeSpec:
    """Specification for one asset type."""

    asset_type: str             # e.g. "HELICOPTER"
    asset_code_prefix: str      # e.g. "AH"
    fleet_weight: float         # relative proportion in fleet (normalised internally)
    components: list[ComponentSpec] = field(default_factory=list)


# ─── Parameter groups ─────────────────────────────────────────────────────────


@dataclass
class DegradationParams:
    """Controls how components degrade over time."""

    # Health decay per operating hour for each archetype
    healthy_rate: float = 0.00002        # ~50 000 h to total failure
    gradual_rate: float = 0.00080        # ~1 250 h
    accelerated_rate: float = 0.00300    # ~333 h
    abrupt_failure_p: float = 0.0005     # probability of sudden step per hour
    nonlinear_knee: float = 0.30         # health level at which degradation accelerates
    nonlinear_exponent: float = 2.5      # acceleration exponent below knee

    # Fleet heterogeneity multipliers (sampled log-normally)
    degradation_multiplier_mu: float = 0.0   # log-mean
    degradation_multiplier_sigma: float = 0.4  # log-std

    # Operating condition modifiers (multiplier on degradation rate)
    condition_multipliers: dict[str, float] = field(default_factory=lambda: {
        "IDLE":                 0.3,
        "CRUISE":               1.0,
        "TAKEOFF":              2.5,
        "COMBAT":               3.5,
        "MAINTENANCE_GROUND":   0.0,
    })


@dataclass
class MaintenanceParams:
    """Controls maintenance scheduling and effects."""

    scheduled_fraction: float = 0.80    # maintenance triggered at MTBF * this fraction
    corrective_trigger_health: float = 0.15  # corrective maintenance below this health
    duration_hours_min: float = 4.0
    duration_hours_max: float = 48.0
    replacement_probability: float = 0.25   # chance of full component replacement
    recovery_timesteps: int = 20            # steps to recover after maintenance
    recovery_health_gain: float = 0.85      # health restored after overhaul
    component_replacement_health: float = 0.97  # health after new component


@dataclass
class MissionParams:
    """Controls mission generation and assignment."""

    mission_interval_days_min: float = 7.0    # min days between missions
    mission_interval_days_max: float = 30.0
    duration_hours_min: float = 4.0
    duration_hours_max: float = 72.0
    criticality_weights: dict[str, float] = field(default_factory=lambda: {
        "LOW": 0.30, "MEDIUM": 0.45, "HIGH": 0.20, "CRITICAL": 0.05,
    })
    assignment_min_health: float = 0.40  # minimum health to assign to a mission


@dataclass
class EdgeCaseParams:
    """Which edge cases to inject and at what rates."""

    inject_missing_telemetry: bool = True
    missing_fraction: float = 0.40             # fraction of readings dropped

    inject_stale_telemetry: bool = True
    stale_duration_steps: int = 30

    inject_stuck_sensor: bool = True
    stuck_duration_steps: int = 60

    inject_outlier: bool = True
    outlier_sigma_multiplier: float = 5.0

    inject_drift: bool = True
    drift_rate_per_step: float = 0.05

    inject_duplicate_timestamp: bool = True

    inject_sensor_failure: bool = True
    sensor_failure_duration_steps: int = 100

    inject_overdue_maintenance: bool = True
    inject_mission_conflict: bool = True
    inject_high_anomaly_low_failure: bool = True
    inject_poor_quality_genuine_degradation: bool = True
    inject_insufficient_data: bool = True
    insufficient_data_max_steps: int = 8


# ─── Fleet profile ────────────────────────────────────────────────────────────


@dataclass
class FleetProfile:
    """Top-level scale / seed configuration."""

    name: str
    n_assets: int
    sim_days: int           # total simulated calendar days
    timestep_hours: float   # hours between telemetry readings (e.g. 1.0)
    seed: int
    description: str = ""


# ─── Master config ────────────────────────────────────────────────────────────


@dataclass
class SimulatorConfig:
    """Complete, self-contained simulator configuration."""

    profile: FleetProfile
    asset_types: list[AssetTypeSpec]
    degradation: DegradationParams = field(default_factory=DegradationParams)
    maintenance: MaintenanceParams = field(default_factory=MaintenanceParams)
    missions: MissionParams = field(default_factory=MissionParams)
    edge_cases: EdgeCaseParams = field(default_factory=EdgeCaseParams)


# ─── Built-in asset type library ──────────────────────────────────────────────

def _default_asset_types() -> list[AssetTypeSpec]:
    """Return the canonical fleet asset type specifications."""

    vibration = SensorSpec(
        sensor_type="VIBRATION_RMS",
        unit="mm/s",
        nominal_min=0.5,
        nominal_max=4.0,
        critical_min=0.0,
        critical_max=20.0,
        noise_sigma=0.15,
        degradation_sensitivity=12.0,
        degradation_direction=1.0,   # rises as health falls
    )
    temperature = SensorSpec(
        sensor_type="TEMP_ENGINE",
        unit="degC",
        nominal_min=60.0,
        nominal_max=120.0,
        critical_min=-20.0,
        critical_max=300.0,
        noise_sigma=1.5,
        degradation_sensitivity=80.0,
        degradation_direction=1.0,   # rises
    )
    pressure = SensorSpec(
        sensor_type="PRESSURE_HYD",
        unit="PSI",
        nominal_min=2500.0,
        nominal_max=3200.0,
        critical_min=0.0,
        critical_max=5000.0,
        noise_sigma=25.0,
        degradation_sensitivity=-1200.0,
        degradation_direction=-1.0,  # drops as health falls
    )
    fan_speed = SensorSpec(
        sensor_type="FAN_SPEED_RPM",
        unit="RPM",
        nominal_min=8000.0,
        nominal_max=12000.0,
        critical_min=0.0,
        critical_max=20000.0,
        noise_sigma=50.0,
        degradation_sensitivity=-2000.0,
        degradation_direction=-1.0,
    )
    bearing_vib = SensorSpec(
        sensor_type="BEARING_VIBRATION",
        unit="mm/s",
        nominal_min=0.2,
        nominal_max=3.0,
        critical_min=0.0,
        critical_max=25.0,
        noise_sigma=0.10,
        degradation_sensitivity=18.0,
        degradation_direction=1.0,
    )
    bearing_temp = SensorSpec(
        sensor_type="BEARING_TEMP",
        unit="degC",
        nominal_min=40.0,
        nominal_max=90.0,
        critical_min=-20.0,
        critical_max=200.0,
        noise_sigma=1.0,
        degradation_sensitivity=60.0,
        degradation_direction=1.0,
    )
    oil_pressure = SensorSpec(
        sensor_type="OIL_PRESSURE",
        unit="PSI",
        nominal_min=40.0,
        nominal_max=80.0,
        critical_min=0.0,
        critical_max=120.0,
        noise_sigma=1.5,
        degradation_sensitivity=-50.0,
        degradation_direction=-1.0,
    )

    helicopter = AssetTypeSpec(
        asset_type="HELICOPTER",
        asset_code_prefix="AH",
        fleet_weight=0.40,
        components=[
            ComponentSpec(
                component_type="ENGINE_CORE",
                name_template="Engine Core",
                mtbf_hours=2000.0,
                mtbf_spread=200.0,
                sensors=[vibration, temperature, fan_speed],
            ),
            ComponentSpec(
                component_type="GEARBOX",
                name_template="Main Gearbox",
                mtbf_hours=1500.0,
                mtbf_spread=150.0,
                sensors=[vibration, bearing_temp],
            ),
            ComponentSpec(
                component_type="HYDRAULICS",
                name_template="Hydraulic System",
                mtbf_hours=3000.0,
                mtbf_spread=300.0,
                sensors=[pressure, oil_pressure],
            ),
        ],
    )
    fixed_wing = AssetTypeSpec(
        asset_type="FIXED_WING",
        asset_code_prefix="FW",
        fleet_weight=0.35,
        components=[
            ComponentSpec(
                component_type="ENGINE_CORE",
                name_template="Turbofan Core",
                mtbf_hours=2500.0,
                mtbf_spread=250.0,
                sensors=[vibration, temperature, pressure],
            ),
            ComponentSpec(
                component_type="BEARING_SET",
                name_template="Fan Bearing Set",
                mtbf_hours=1800.0,
                mtbf_spread=180.0,
                sensors=[bearing_vib, bearing_temp],
            ),
        ],
    )
    ground_vehicle = AssetTypeSpec(
        asset_type="GROUND_VEHICLE",
        asset_code_prefix="GV",
        fleet_weight=0.25,
        components=[
            ComponentSpec(
                component_type="ENGINE_CORE",
                name_template="Drive Engine",
                mtbf_hours=1200.0,
                mtbf_spread=120.0,
                sensors=[temperature, oil_pressure],
            ),
            ComponentSpec(
                component_type="HYDRAULICS",
                name_template="Drive Hydraulics",
                mtbf_hours=2000.0,
                mtbf_spread=200.0,
                sensors=[pressure, oil_pressure],
            ),
        ],
    )

    return [helicopter, fixed_wing, ground_vehicle]


# ─── YAML profile loader ──────────────────────────────────────────────────────

def _dict_to_fleet_profile(d: dict[str, Any]) -> FleetProfile:
    return FleetProfile(
        name=d["name"],
        n_assets=int(d["n_assets"]),
        sim_days=int(d["sim_days"]),
        timestep_hours=float(d.get("timestep_hours", 1.0)),
        seed=int(d["seed"]),
        description=d.get("description", ""),
    )


def _dict_to_degradation(d: dict[str, Any]) -> DegradationParams:
    p = DegradationParams()
    for k, v in d.items():
        if hasattr(p, k):
            setattr(p, k, v)
    return p


def _dict_to_maintenance(d: dict[str, Any]) -> MaintenanceParams:
    p = MaintenanceParams()
    for k, v in d.items():
        if hasattr(p, k):
            setattr(p, k, v)
    return p


def _dict_to_missions(d: dict[str, Any]) -> MissionParams:
    p = MissionParams()
    for k, v in d.items():
        if hasattr(p, k):
            setattr(p, k, v)
    return p


def _dict_to_edge_cases(d: dict[str, Any]) -> EdgeCaseParams:
    p = EdgeCaseParams()
    for k, v in d.items():
        if hasattr(p, k):
            setattr(p, k, v)
    return p


def load_profile(profile_name: str) -> SimulatorConfig:
    """Load a named simulator profile from YAML.

    Parameters
    ----------
    profile_name:
        One of "tiny", "validation", "demo" — or path to a custom YAML file.

    Returns
    -------
    SimulatorConfig
        Fully populated simulator configuration.
    """
    path = PROFILES_DIR / f"{profile_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Profile '{profile_name}' not found at {path}. "
            f"Available: {[p.stem for p in PROFILES_DIR.glob('*.yaml')]}"
        )

    with path.open() as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    profile = _dict_to_fleet_profile(raw["profile"])
    degradation = _dict_to_degradation(raw.get("degradation", {}))
    maintenance = _dict_to_maintenance(raw.get("maintenance", {}))
    missions = _dict_to_missions(raw.get("missions", {}))
    edge_cases = _dict_to_edge_cases(raw.get("edge_cases", {}))

    return SimulatorConfig(
        profile=profile,
        asset_types=_default_asset_types(),
        degradation=degradation,
        maintenance=maintenance,
        missions=missions,
        edge_cases=edge_cases,
    )


def default_config(
    n_assets: int = 10,
    sim_days: int = 365,
    seed: int = 42,
    timestep_hours: float = 1.0,
) -> SimulatorConfig:
    """Build a default SimulatorConfig without loading a YAML file."""
    return SimulatorConfig(
        profile=FleetProfile(
            name="default",
            n_assets=n_assets,
            sim_days=sim_days,
            timestep_hours=timestep_hours,
            seed=seed,
        ),
        asset_types=_default_asset_types(),
    )
