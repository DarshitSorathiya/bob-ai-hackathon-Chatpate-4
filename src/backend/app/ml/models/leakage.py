"""
Pre-training leakage guard.

Runs before any model is trained or evaluated. Raises LeakageError if
any forbidden column is detected in the feature matrix, or if the
label column appears in X.

This is the single authoritative check — all training entrypoints must
call LeakageGuard.check() before fitting.
"""

from __future__ import annotations

import pandas as pd


# Columns that must never appear in any feature matrix passed to a model.
# This is the union of:
#   - simulator truth columns (never observable)
#   - label columns for all three tasks
#   - future-derived columns
FORBIDDEN_COLUMNS: frozenset[str] = frozenset({
    # Simulator truth
    "true_health",
    "true_rul",
    "latent_health",
    "degradation_multiplier",
    "archetype",
    # Label columns (all tasks)
    "rul_cycles",
    "failure_within_24h",
    "failure_within_72h",
    "failure_within_window",
    "health_class",
    # Raw pipeline guard columns
    "failure_label",
    "failure_event",
    "failure_timestamp",
    # Any future-derived column from the truth layer
    "failure_events",
})

# Label columns that must not appear in X (keyed by task name)
TASK_LABEL_COLUMNS: dict[str, frozenset[str]] = {
    "rul": frozenset({"rul_cycles", "true_rul"}),
    "failure": frozenset({
        "failure_within_24h", "failure_within_72h", "failure_within_window",
        "failure_label", "failure_event",
    }),
    "anomaly": frozenset({"true_health", "latent_health", "health_class"}),
}


class LeakageError(Exception):
    """Raised when a leakage violation is detected in the feature matrix."""


class LeakageGuard:
    """Stateless leakage checker. Call before every model fit."""

    @staticmethod
    def check(
        X: pd.DataFrame,
        y_col: str | None = None,
        task: str | None = None,
    ) -> None:
        """Raise LeakageError if any forbidden column is present in X.

        Parameters
        ----------
        X:
            Feature matrix.
        y_col:
            Name of the label column. Must not appear in X.
        task:
            One of 'rul', 'failure', 'anomaly'. Additional task-specific
            label columns are checked if provided.
        """
        violations: list[str] = []

        # Global forbidden columns
        for col in FORBIDDEN_COLUMNS:
            if col in X.columns:
                violations.append(f"Global forbidden column in X: '{col}'")

        # Task-specific label columns
        if task and task in TASK_LABEL_COLUMNS:
            for col in TASK_LABEL_COLUMNS[task]:
                if col in X.columns:
                    violations.append(
                        f"Task '{task}' label column in X: '{col}'"
                    )

        # Explicit y_col
        if y_col and y_col in X.columns:
            violations.append(f"Label column '{y_col}' is also in X")

        if violations:
            msg = "LEAKAGE DETECTED — training aborted:\n" + "\n".join(
                f"  • {v}" for v in violations
            )
            raise LeakageError(msg)

    @staticmethod
    def report(
        X: pd.DataFrame,
        y_col: str | None = None,
        task: str | None = None,
    ) -> list[str]:
        """Return violations without raising. Empty list = clean."""
        violations: list[str] = []
        for col in FORBIDDEN_COLUMNS:
            if col in X.columns:
                violations.append(f"Global forbidden column in X: '{col}'")
        if task and task in TASK_LABEL_COLUMNS:
            for col in TASK_LABEL_COLUMNS[task]:
                if col in X.columns:
                    violations.append(
                        f"Task '{task}' label column in X: '{col}'"
                    )
        if y_col and y_col in X.columns:
            violations.append(f"Label column '{y_col}' is also in X")
        return violations
