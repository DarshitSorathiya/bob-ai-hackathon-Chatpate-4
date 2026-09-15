#!/usr/bin/env python3
"""
Seed script — populate the database with realistic demo data.

Usage (from src/backend/):
    python scripts/seed_demo_data.py
    python scripts/seed_demo_data.py --reset   # drops existing data first

What is created:
    3 assets (1 helicopter, 1 fixed-wing, 1 ground vehicle)
    2 components per asset (6 total)
    2 sensors per component (12 total)
    1 mission (PLANNED, 2 requirements)
    3 work orders (OPEN, IMMEDIATE + URGENT + SCHEDULED)
    3 alerts (ACTIVE, critical + warning + info)
    3 data quality events
    1 AssetReadiness record per asset (seeded as UNKNOWN — run /readiness/evaluate to update)

No predictions or telemetry rows are written by this script; those come from the
ML pipeline (simulator or real data ingestion).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make sure we can import app modules when run from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database import engine, Base
from app.core.logging import configure_logging
from app.models import *  # noqa: F401,F403 — register all ORM models with Base
from app.models.fleet import Asset, Component, Sensor
from app.models.operations import (
    Alert,
    AssetReadiness,
    Mission,
    MissionRequirement,
    WorkOrder,
)
from app.models.telemetry import DataQualityEvent

configure_logging("WARNING")


# ─── Demo fixture data ─────────────────────────────────────────────────────────

ASSETS = [
    dict(
        asset_code="AH-64-01",
        asset_type="HELICOPTER",
        call_sign="Ghost 1",
        description="AH-64 Apache — primary attack helicopter",
        manufacturer="Boeing",
        model_number="AH-64E",
        serial_number="SN-AH64-001",
        total_hours=1247.5,
        is_active=True,
    ),
    dict(
        asset_code="F-16-01",
        asset_type="FIXED_WING",
        call_sign="Viper Lead",
        description="F-16 Fighting Falcon — multi-role fighter",
        manufacturer="Lockheed Martin",
        model_number="F-16C Block 50",
        serial_number="SN-F16-001",
        total_hours=3821.0,
        is_active=True,
    ),
    dict(
        asset_code="HMMWV-01",
        asset_type="GROUND_VEHICLE",
        call_sign="Bravo 1",
        description="M1151 HMMWV — armoured utility vehicle",
        manufacturer="AM General",
        model_number="M1151A1",
        serial_number="SN-HMMWV-001",
        total_hours=8540.0,
        is_active=True,
    ),
]

COMPONENTS = {
    "AH-64-01": [
        dict(component_code="AH64-01-ENG", component_type="ENGINE",   name="T700 Engine",           criticality="CRITICAL"),
        dict(component_code="AH64-01-RTR", component_type="ROTOR",    name="Main Rotor Assembly",   criticality="CRITICAL"),
    ],
    "F-16-01": [
        dict(component_code="F16-01-ENG",  component_type="ENGINE",   name="F110-GE-129 Engine",    criticality="CRITICAL"),
        dict(component_code="F16-01-AVN",  component_type="AVIONICS", name="APG-68 Radar",          criticality="HIGH"),
    ],
    "HMMWV-01": [
        dict(component_code="HMMWV-01-ENG", component_type="ENGINE",  name="6.5L Diesel Engine",    criticality="HIGH"),
        dict(component_code="HMMWV-01-TRN", component_type="TRANSMISSION", name="Automatic Transmission", criticality="MEDIUM"),
    ],
}

SENSORS = {
    "AH64-01-ENG": [
        dict(sensor_code="AH64-01-ENG-TGT", sensor_type="TEMPERATURE", name="TGT Sensor",         unit="°C", nominal_min=400.0, nominal_max=850.0, critical_min=300.0, critical_max=950.0),
        dict(sensor_code="AH64-01-ENG-TRQ", sensor_type="TORQUE",      name="Engine Torque",       unit="%",  nominal_min=0.0,   nominal_max=100.0,  critical_min=0.0,   critical_max=110.0),
    ],
    "AH64-01-RTR": [
        dict(sensor_code="AH64-01-RTR-VIB", sensor_type="VIBRATION",   name="Main Rotor Vibration", unit="mm/s", nominal_min=0.0, nominal_max=12.0, critical_min=0.0, critical_max=25.0),
        dict(sensor_code="AH64-01-RTR-RPM", sensor_type="RPM",          name="Rotor RPM",            unit="rpm",  nominal_min=258.0, nominal_max=262.0, critical_min=240.0, critical_max=270.0),
    ],
    "F16-01-ENG": [
        dict(sensor_code="F16-01-ENG-EGT",  sensor_type="TEMPERATURE", name="EGT Sensor",           unit="°C", nominal_min=400.0, nominal_max=900.0, critical_min=300.0, critical_max=1050.0),
        dict(sensor_code="F16-01-ENG-N2",   sensor_type="RPM",          name="N2 Compressor RPM",    unit="%",  nominal_min=80.0,  nominal_max=105.0,  critical_min=60.0,  critical_max=110.0),
    ],
    "F16-01-AVN": [
        dict(sensor_code="F16-01-AVN-PWR",  sensor_type="POWER",       name="Avionics Bus Voltage", unit="V",  nominal_min=27.5, nominal_max=28.5, critical_min=26.0, critical_max=30.0),
        dict(sensor_code="F16-01-AVN-TMP",  sensor_type="TEMPERATURE", name="Avionics Bay Temp",    unit="°C", nominal_min=-20.0, nominal_max=60.0, critical_min=-40.0, critical_max=85.0),
    ],
    "HMMWV-01-ENG": [
        dict(sensor_code="HMMWV-01-ENG-OTP", sensor_type="PRESSURE",    name="Oil Pressure",         unit="kPa", nominal_min=207.0, nominal_max=517.0, critical_min=138.0, critical_max=620.0),
        dict(sensor_code="HMMWV-01-ENG-CLT", sensor_type="TEMPERATURE", name="Coolant Temp",          unit="°C",  nominal_min=80.0, nominal_max=100.0, critical_min=60.0, critical_max=120.0),
    ],
    "HMMWV-01-TRN": [
        dict(sensor_code="HMMWV-01-TRN-TMP", sensor_type="TEMPERATURE", name="Trans Fluid Temp",     unit="°C", nominal_min=60.0, nominal_max=90.0, critical_min=40.0, critical_max=120.0),
        dict(sensor_code="HMMWV-01-TRN-PRS", sensor_type="PRESSURE",    name="Trans Line Pressure",  unit="kPa", nominal_min=800.0, nominal_max=1200.0, critical_min=600.0, critical_max=1400.0),
    ],
}

NOW = datetime.now(timezone.utc)


def seed(session, reset: bool = False) -> None:
    if reset:
        print("Resetting existing demo data...")
        for model in [DataQualityEvent, Alert, WorkOrder, MissionRequirement, Mission,
                      AssetReadiness, Sensor, Component, Asset]:
            count = session.query(model).delete()
            print(f"  Deleted {count} {model.__tablename__} rows")
        session.commit()

    # Check if already seeded
    existing = session.query(Asset).filter(Asset.asset_code == "AH-64-01").first()
    if existing and not reset:
        print("Demo data already exists. Use --reset to re-seed.")
        return

    print("Seeding assets...")
    asset_map: dict[str, Asset] = {}
    for a_data in ASSETS:
        asset = Asset(**a_data)
        session.add(asset)
        session.flush()
        asset_map[a_data["asset_code"]] = asset
        print(f"  + Asset {a_data['asset_code']}")

    print("Seeding components and sensors...")
    comp_map: dict[str, Component] = {}
    for asset_code, comp_list in COMPONENTS.items():
        asset = asset_map[asset_code]
        for c_data in comp_list:
            comp = Component(asset_id=asset.id, **c_data)
            session.add(comp)
            session.flush()
            comp_map[c_data["component_code"]] = comp

            for s_data in SENSORS.get(c_data["component_code"], []):
                sensor = Sensor(asset_id=asset.id, component_id=comp.id, is_active=True, **s_data)
                session.add(sensor)
            print(f"    + Component {c_data['component_code']}")

    print("Seeding mission...")
    mission = Mission(
        mission_code="OPE-NIGHTHAWK-01",
        name="Operation Nighthawk",
        description="Reconnaissance sweep — northern sector. Duration 4 hours. Requires 1 attack helicopter and 1 fixed-wing asset.",
        status="PLANNED",
        priority="HIGH",
        planned_start=NOW + timedelta(days=2),
        planned_end=NOW + timedelta(days=2, hours=4),
        duration_hours=4.0,
        location="Northern Sector Grid 4-7",
    )
    session.add(mission)
    session.flush()
    session.add(MissionRequirement(mission_id=mission.id, capability="HELICOPTER", required_count=1, is_critical=True))
    session.add(MissionRequirement(mission_id=mission.id, capability="FIXED_WING", required_count=1, is_critical=True))
    print(f"  + Mission {mission.mission_code}")

    print("Seeding work orders...")
    ah64 = asset_map["AH-64-01"]
    f16  = asset_map["F-16-01"]
    hmmwv = asset_map["HMMWV-01"]

    session.add(WorkOrder(
        title="AH-64-01: Main rotor vibration exceeds threshold — inspect and balance",
        description="HUMS vibration sensor AH64-01-RTR-VIB reading 18.3 mm/s (nominal max 12.0). Inspect rotor blade tracking and balance before next sortie.",
        asset_id=ah64.id,
        status="OPEN",
        urgency_level="IMMEDIATE",
        is_blocking=True,
        estimated_hours=6.0,
    ))
    session.add(WorkOrder(
        title="F-16-01: EGT trending high — borescope engine hot section",
        description="Exhaust gas temperature trending +22°C above 30-day baseline over 47 flight hours. Borescope inspection recommended.",
        asset_id=f16.id,
        status="OPEN",
        urgency_level="URGENT",
        is_blocking=False,
        estimated_hours=4.0,
    ))
    session.add(WorkOrder(
        title="HMMWV-01: 10,000 km scheduled engine service",
        description="Routine 10,000 km service: oil change, filter replacement, belt inspection, coolant flush.",
        asset_id=hmmwv.id,
        status="OPEN",
        urgency_level="SCHEDULED",
        is_blocking=False,
        estimated_hours=3.0,
    ))
    print("  + 3 work orders")

    print("Seeding alerts...")
    session.add(Alert(
        asset_id=ah64.id,
        alert_type="VIBRATION_THRESHOLD",
        severity="critical",
        title="AH-64-01 Main Rotor Vibration CRITICAL",
        message="Rotor vibration sensor reading 18.3 mm/s — exceeds critical threshold of 15.0 mm/s. Immediate ground inspection required.",
        status="ACTIVE",
    ))
    session.add(Alert(
        asset_id=f16.id,
        alert_type="TEMPERATURE_TREND",
        severity="warning",
        title="F-16-01 EGT Trending Above Baseline",
        message="Exhaust gas temperature trending +22°C above 30-day baseline over 47 flight hours.",
        status="ACTIVE",
    ))
    session.add(Alert(
        asset_id=hmmwv.id,
        alert_type="MAINTENANCE_DUE",
        severity="info",
        title="HMMWV-01 Scheduled Service Due",
        message="Vehicle has reached 10,000 km service interval. Schedule maintenance within 500 km.",
        status="ACTIVE",
    ))
    print("  + 3 alerts")

    print("Seeding data quality events...")
    session.add(DataQualityEvent(
        asset_id=ah64.id,
        event_type="FAULT",
        severity="critical",
        description="AH64-01-RTR-VIB: sensor output spikes detected — possible loose mounting or signal cable fault.",
        is_resolved=False,
    ))
    session.add(DataQualityEvent(
        asset_id=f16.id,
        event_type="DRIFT",
        severity="warning",
        description="F16-01-ENG-EGT: calibration drift of +8°C detected against reference sensor over 30-day window.",
        is_resolved=False,
    ))
    session.add(DataQualityEvent(
        asset_id=hmmwv.id,
        event_type="STALE",
        severity="info",
        description="HMMWV-01-TRN-PRS: no telemetry received for 72 hours — vehicle may be offline or sensor disconnected.",
        is_resolved=False,
    ))
    print("  + 3 data quality events")

    print("Seeding readiness records (UNKNOWN — run /readiness/evaluate/{id} to update)...")
    for asset in asset_map.values():
        session.add(AssetReadiness(
            asset_id=asset.id,
            status="UNKNOWN",
            confidence=0.0,
            primary_reason="INSUFFICIENT_DATA",
        ))
    print("  + 3 readiness records")

    session.commit()
    print("\n✅ Demo data seeded successfully.")
    print(f"   Assets: {len(ASSETS)}")
    print(f"   Components: {sum(len(v) for v in COMPONENTS.values())}")
    print(f"   Sensors: {sum(len(v) for v in SENSORS.values())}")
    print("   Missions: 1")
    print("   Work Orders: 3")
    print("   Alerts: 3")
    print("   Data Quality Events: 3")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data into MissionReady AI database")
    parser.add_argument("--reset", action="store_true", help="Delete existing data before seeding")
    args = parser.parse_args()

    from sqlalchemy.orm import Session
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed(session, reset=args.reset)


if __name__ == "__main__":
    main()
