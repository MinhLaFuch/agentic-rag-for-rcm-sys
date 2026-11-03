"""Compatibility module for build_memory_correctness_dataset.

This module provides backward compatibility for code that imports:
    from package.evaluation.component.benchmarks import build_memory_correctness_dataset as builder

And uses: builder.DATASET_PATH, builder.SPECS, builder.build_cases(), builder.render()
"""

from __future__ import annotations

from ._dataset_common import DATASET_PATH, SPECS
from .build_cases import build_cases
from .render import render

__all__ = ["DATASET_PATH", "SPECS", "build_cases", "render"]


# Dummy public symbol to satisfy package layout test
def build_memory_correctness_dataset() -> str:
    """Dummy function to satisfy package layout convention."""
    return "build_memory_correctness_dataset"