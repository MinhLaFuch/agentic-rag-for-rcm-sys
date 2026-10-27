"""Executor and Reflection benchmark.

Tests:
- Reference resolution
- Error handling
- Retry behavior
- Reflection contribution
"""

from __future__ import annotations

import time
from typing import Any

from package.agents.planner import PlanExecutor
from package.evaluation.component._evaluator import ComponentEvaluator

from .executor_mock_tools import get_controlled_tools
from .planner_mock_llm import get_mock_llm


class ExecutorBenchmark(ComponentEvaluator):
    """Evaluator for PlanExecutor with reflection analysis."""

    component_name = "executor"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.llm = get_mock_llm()
        self.reflect_rounds = self.config.get("reflect_rounds", 2)
        self.executor = PlanExecutor(llm=self.llm, tools=[], reflect_rounds=self.reflect_rounds)

    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Run executor with controlled tools and capture reflection data."""
        steps = case_input.get("steps", [])
        tool_config = case_input.get("tool_config", {})
        user_request = case_input.get("user_request", "")

        # Set up controlled tools
        self.executor.tools = {t.name: t for t in get_controlled_tools(tool_config)}
        self.executor.reflect_rounds = self.reflect_rounds

        started = time.perf_counter()

        try:
            # Run first attempt
            first_results = self.executor._execute(steps, user_request)
            first_ok = all(r.get("ok") for r in first_results) if first_results else False
            
            # If first failed and reflection is enabled, try again (simplified reflection)
            results = first_results
            reflections_used = 0
            if not first_ok and self.reflect_rounds > 0:
                # Reset tools for retry
                self.executor.tools = {t.name: t for t in get_controlled_tools(tool_config)}
                results = self.executor._execute(steps, user_request)
                reflections_used = 1
            
            after_ok = all(r.get("ok") for r in results) if results else False
            
            return {
                "first_attempt_ok": first_ok,
                "after_reflection_ok": after_ok,
                "reflections_used": reflections_used,
                "latency_seconds": time.perf_counter() - started,
            }
        except Exception as e:
            return {
                "error": str(e),
                "latency_seconds": time.perf_counter() - started,
            }

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score executor output and reflection contribution."""
        if "error" in actual_output:
            return {
                "all_steps_ok": 0.0,
                "reflection_rescued": 0.0,
                "reflection_worsened": 0.0,
                "reflection_no_change": 0.0,
                "reflection_triggered": 0.0,
            }

        first_ok = actual_output.get("first_attempt_ok", False)
        after_ok = actual_output.get("after_reflection_ok", False)
        reflections_used = actual_output.get("reflections_used", 0)

        metrics = {
            "all_steps_ok": 1.0 if after_ok else 0.0,
            "reflection_rescued": 0.0,
            "reflection_worsened": 0.0,
            "reflection_no_change": 0.0,
            "reflection_triggered": 1.0 if reflections_used > 0 else 0.0,
        }

        # Calculate reflection contribution
        if reflections_used > 0:
            if not first_ok and after_ok:
                metrics["reflection_rescued"] = 1.0  # fail → pass
            elif first_ok and not after_ok:
                metrics["reflection_worsened"] = 1.0  # pass → fail
            else:
                metrics["reflection_no_change"] = 1.0  # no change
        else:
            metrics["reflection_no_change"] = 1.0  # no reflection = no change

        return metrics
