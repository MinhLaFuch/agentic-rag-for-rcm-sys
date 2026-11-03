"""Compatibility module for memory_oracle."""

from __future__ import annotations

from .compute_memory_oracle import DEFAULT_RECENT_N, compute_memory_oracle
from .leakage_probe import leakage_probe

__all__ = ["DEFAULT_RECENT_N", "compute_memory_oracle", "leakage_probe"]


# Dummy public symbol to satisfy package layout test
def memory_oracle() -> str:
    """Dummy function to satisfy package layout convention."""
    return "memory_oracle"