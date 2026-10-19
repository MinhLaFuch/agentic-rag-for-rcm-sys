"""Latency summary metrics for evaluation runs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def latency_summary(values: Sequence[float]) -> dict[str, float | int]:
    """Return stable latency summaries in seconds for a sequence of timed operations."""
    timings = np.asarray(values, dtype=np.float64)
    if timings.ndim != 1 or not np.isfinite(timings).all() or np.any(timings < 0):
        raise ValueError("latencies must be finite, non-negative values")
    if not len(timings):
        return {"calls": 0, "total_seconds": 0.0, "mean_seconds": 0.0, "p50_seconds": 0.0, "p95_seconds": 0.0}
    return {
        "calls": int(len(timings)),
        "total_seconds": float(timings.sum()),
        "mean_seconds": float(timings.mean()),
        "p50_seconds": float(np.percentile(timings, 50)),
        "p95_seconds": float(np.percentile(timings, 95)),
    }
