"""Helper functions for evaluation module."""

from __future__ import annotations

import subprocess

import numpy as np


def _git_commit() -> str | None:
    """Get current git commit hash if available."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def assign_segments(history_sizes: np.ndarray, sparse_max: int) -> np.ndarray:
    """Assign user segments based on interaction history size."""
    return np.where(
        history_sizes == 0, "cold", np.where(history_sizes <= sparse_max, "sparse", "warm")
    )
