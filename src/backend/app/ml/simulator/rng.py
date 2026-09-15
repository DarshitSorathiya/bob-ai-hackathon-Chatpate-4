"""
Deterministic random-number management for the fleet simulator.

All randomness in the simulator flows through RNGManager. Each entity
(asset, component, sensor) receives a child RNG seeded deterministically
from the master seed and a stable entity key. This guarantees:

  - Identical output for identical seeds.
  - Adding more assets does not change the RNG stream of existing ones
    (each entity owns its own independent stream).
  - No global numpy/random state is mutated.
"""

from __future__ import annotations

import hashlib

import numpy as np


class RNGManager:
    """Manages a hierarchy of independent, deterministic RNG streams.

    Usage
    -----
    rng = RNGManager(seed=42)
    asset_rng  = rng.child("asset", "AH-01")
    comp_rng   = rng.child("component", "AH-01/ENGINE_CORE")
    sensor_rng = rng.child("sensor", "AH-01/ENGINE_CORE/VIBRATION_RMS")

    Each child returns a numpy Generator seeded deterministically from
    the combination of the master seed and the entity key.  The same key
    always produces the same generator, regardless of call order.
    """

    def __init__(self, seed: int) -> None:
        self._master_seed = seed
        self._cache: dict[str, np.random.Generator] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def child(self, *key_parts: str) -> np.random.Generator:
        """Return a deterministic Generator for the given key path.

        Parameters
        ----------
        key_parts:
            Arbitrary string parts that together uniquely identify an entity,
            e.g. ("asset", "AH-01") or ("sensor", "AH-01", "ENGINE_CORE", "VIB").
        """
        key = "/".join(str(p) for p in key_parts)
        if key not in self._cache:
            self._cache[key] = self._make_generator(key)
        return self._cache[key]

    def fleet(self) -> np.random.Generator:
        """Generator for fleet-level decisions (asset count, type distribution)."""
        return self.child("__fleet__")

    def edge_case(self, label: str) -> np.random.Generator:
        """Generator for a specific edge-case injector."""
        return self.child("__edge__", label)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_generator(self, key: str) -> np.random.Generator:
        """Create a Generator seeded from master seed + key hash."""
        # Combine master seed with a hash of the key to produce a child seed.
        # Using SHA-256 gives us 256 bits of uniqueness; we take the first 8
        # bytes (uint64) as the child seed.
        h = hashlib.sha256(f"{self._master_seed}:{key}".encode()).digest()
        child_seed = int.from_bytes(h[:8], byteorder="little")
        return np.random.default_rng(child_seed)

    @property
    def master_seed(self) -> int:
        return self._master_seed
