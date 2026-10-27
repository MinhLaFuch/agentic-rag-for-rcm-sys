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
        """Run executor with controlled tools."""
        steps = case_input.get("steps", [])
        tool_config = case_input.get("tool_config", {})
        user_request = case_input.get("user_request", "")

        # Set up controlled tools
        self.executor.tools = {t.name: t for t in get_controlled_tools(tool_config)}
        self.executor.reflect_rounds = self.reflect_rounds

        started = time.perf_counter()

        try:
            # Run with reflection
            results = self.executor._execute(steps, user_request)
            
            return {
                "results": results,
                "first_attempt_ok": self.executor.last_first_attempt_ok,
                "reflections_used": self.executor.last_reflections,
                "attempts": len(self.executor.last_attempt_plans),
                "latency_seconds": time.perf_counter() - started,
            }
        except Exception as e:
            return {
                "results": [],
                "error": str(e),
                "latency_seconds": time.perf_counter() - started,
            }

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score executor output."""
        results = actual_output.get("results", [])
        
        metrics = {
            "all_steps_ok": 0.0,
            "no_invented_ids": 0.0,
            "references_resolved": 0.0,
            "tool_error_handled": 0.0,
            "empty_output_handled": 0.0,
            "reference_error": 0.0,
            "reflection_triggered": 0.0,
            "reflections_within_limit": 0.0,
        }

        if "error" in actual_output:
            return metrics

        # Check if all steps ok
        metrics["all_steps_ok"] = 1.0 if all(r.get("ok") for r in results) else 0.0

        # Check for invented IDs
        metrics["no_invented_ids"] = 1.0 if not any(r.get("invented_ids") for r in results) else 0.0

        # Check references resolved
        bad_refs = [r for r in results if r.get("error_kind") == "bad_reference"]
        metrics["references_resolved"] = 1.0 if not bad_refs else 0.0

        # Check tool error handling
        tool_errors = [r for r in results if r.get("error_kind") == "tool_error"]
        metrics["tool_error_handled"] = 1.0 if not tool_errors else 0.0

        # Check empty output handling
        empty_outputs = [r for r in results if not r.get("ok") and "empty" in str(r.get("error", "")).lower()]
        metrics["empty_output_handled"] = 1.0 if not empty_outputs else 0.0

        # Check reference error detection
        metrics["reference_error"] = 1.0 if bad_refs else 0.0

        # Check reflection triggered
        metrics["reflection_triggered"] = 1.0 if actual_output.get("reflections_used", 0) > 0 else 0.0

        # Check reflections within limit
        metrics["reflections_within_limit"] = 1.0 if actual_output.get("reflections_used", 0) <= self.reflect_rounds else 0.0

        return metrics
