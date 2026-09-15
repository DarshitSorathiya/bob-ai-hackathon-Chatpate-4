"""
MissionReady AI — Synthetic Digital Fleet Simulator.

Causal chain:
  latent true state
      ↓  degradation process
      ↓  ideal physical signal
      ↓  operating/environment effects
      ↓  sensor characteristics
      ↓  noise
      ↓  sensor/data-quality faults
      ↓  observed telemetry

The simulator maintains a strict separation between truth (latent health,
true RUL, future failure timestamps) and observable data (what the ML
pipeline is allowed to see).

Public API
----------
  from app.ml.simulator import FleetSimulator, SimulatorConfig, load_profile

  cfg = load_profile("tiny")
  sim = FleetSimulator(cfg)
  result = sim.run()       # SimulationResult
  result.observable        # dict[str, pd.DataFrame] — ML-visible tables
  result.truth             # dict[str, pd.DataFrame] — labels only (never feature input)
"""

from app.ml.simulator.config import SimulatorConfig, load_profile
from app.ml.simulator.engine import FleetSimulator
from app.ml.simulator.export import SimulationResult

__all__ = ["FleetSimulator", "SimulatorConfig", "SimulationResult", "load_profile"]
