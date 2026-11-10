"""Component-level evaluation framework for individual components (Memory, Planner, Executor, Reflection, Inference, Grounding)."""

from __future__ import annotations

from ._run_all import main as run_component_benchmarks

__all__ = ["run_component_benchmarks"]
