#!/usr/bin/env python3
"""Run the background fleet lifecycle loop."""
from __future__ import annotations

import argparse
import logging
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal, create_tables
from app.services.lifecycle_service import FleetLifecycleService


def main() -> None:
    parser = argparse.ArgumentParser(description="Advance fleet telemetry and readiness in the background")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between lifecycle ticks")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    create_tables()
    service = FleetLifecycleService()
    while True:
        with SessionLocal() as db:
            summary = service.tick(db)
            logging.info("lifecycle_tick %s", summary)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()