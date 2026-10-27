"""Planner benchmark: isolated evaluation of plan-first planning.

Tests:
- Tool selection accuracy
- Argument correctness & completeness
- Plan/schema validity
- Reference resolution ($N.path)
- Constraint handling
- Clarification behavior (ask_user)
- Refusal-to-guess (must-not-guess cases)
- Stability across runs
- Latency and token/cost
"""

from __future__ import annotations

import os
import time
from typing import Any

from package.agents.planner import PlanExecutor
from package.api import build_llm_provider
from package.evaluation.component._evaluator import ComponentEvaluator
from package.evaluation.component._schema import BenchmarkCase, BenchmarkResult

from .planner_mock_tools import get_mock_tools


class PlannerBenchmark(ComponentEvaluator):
    """Evaluator for Planner (PlanExecutor) component."""

    component_name = "planner"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        
        # Load LLM config from file or use provided config
        llm_config = self.config.get("llm", {})
        if not llm_config:
            # Try to load from default config file
            import yaml
            config_path = "configs/agent/llm.yaml"
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    llm_config = yaml.safe_load(f)
                    # Substitute environment variables
                    base_url = llm_config.get("base_url", "")
                    if "${LLM_BASE_URL:-}" in base_url or base_url.startswith("${"):
                        base_url = os.environ.get("LLM_BASE_URL", "")
                    llm_config["base_url"] = base_url
                    
                    api_key = llm_config.get("api_key", "")
                    if "${LLM_API_KEY:-}" in api_key or api_key.startswith("${"):
                        api_key = os.environ.get("LLM_API_KEY", "")
                    llm_config["api_key"] = api_key
        
        if not llm_config.get("base_url"):
            raise ValueError(
                "LLM base_url not configured. Set LLM_BASE_URL environment variable "
                "or provide llm.base_url in config (e.g., --config '{\"llm\": {\"base_url\": \"https://...\", \"model\": \"...\"}}')."
            )
        
        self.llm = build_llm_provider(llm_config)
        self.tools = get_mock_tools()
        self.executor = PlanExecutor(llm=self.llm, tools=self.tools, reflect_rounds=0)

    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Run Planner with mock tools."""
        user_request = case_input.get("user_request", "")
        started = time.perf_counter()

        try:
            steps = self.executor.plan(user_request)
            question = self.executor.last_question
            latency = time.perf_counter() - started

            return {
                "steps": steps,
                "question": question,
                "latency_seconds": latency,
                "usage": self.executor.last_usage,
            }
        except Exception as e:
            return {
                "steps": [],
                "question": None,
                "error": str(e),
                "latency_seconds": time.perf_counter() - started,
            }

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score planner output against expected."""
        actual_steps = actual_output.get("steps", [])
        actual_question = actual_output.get("question")
        expected_steps = expected.get("steps", [])
        expected_question = expected.get("question")

        metrics = {
            "tool_selection_accuracy": 0.0,
            "argument_correctness": 0.0,
            "plan_validity": 0.0,
            "reference_correctness": 0.0,
            "constraint_handling": 0.0,
            "clarification_precision": 0.0,
            "clarification_recall": 0.0,
            "refusal_to_guess": 0.0,
        }

        # If there's an error, all metrics are 0
        if "error" in actual_output:
            return metrics

        # Check if expected question matches (for ambiguous cases)
        if expected_question is not None:
            metrics["clarification_precision"] = 1.0 if actual_question == expected_question else 0.0
            metrics["clarification_recall"] = 1.0 if actual_question is not None else 0.0
        else:
            # Should not ask question
            metrics["clarification_precision"] = 1.0 if actual_question is None else 0.0
            metrics["clarification_recall"] = 1.0

        # Tool selection accuracy
        if len(actual_steps) == len(expected_steps):
            correct_tools = sum(
                1 for a, e in zip(actual_steps, expected_steps) if a.get("tool") == e.get("tool")
            )
            metrics["tool_selection_accuracy"] = correct_tools / len(expected_steps) if expected_steps else 1.0

        # Argument correctness (simple field match)
        if len(actual_steps) == len(expected_steps):
            correct_args = 0
            total_args = 0
            for a, e in zip(actual_steps, expected_steps):
                a_args = a.get("args", {})
                e_args = e.get("args", {})
                for key in e_args:
                    total_args += 1
                    if a_args.get(key) == e_args.get(key):
                        correct_args += 1
            metrics["argument_correctness"] = correct_args / total_args if total_args > 0 else 1.0

        # Plan validity (is it a valid list of steps)
        metrics["plan_validity"] = 1.0 if isinstance(actual_steps, list) and all(isinstance(s, dict) for s in actual_steps) else 0.0

        # Refusal to guess (if expected asks for clarification, treat as refusal)
        if expected_question is not None:
            metrics["refusal_to_guess"] = 1.0 if actual_question is not None else 0.0
        else:
            metrics["refusal_to_guess"] = 1.0

        # Reference correctness (check if $N.path format is used correctly)
        # Simplified: just check if references are present when expected
        has_references = any("$" in str(a.get("args", {})) for a in actual_steps)
        expected_references = any("$" in str(e.get("args", {})) for e in expected_steps)
        metrics["reference_correctness"] = 1.0 if has_references == expected_references else 0.0

        # Constraint handling (check if filters match expected)
        if len(actual_steps) == len(expected_steps):
            correct_filters = 0
            total_filters = 0
            for a, e in zip(actual_steps, expected_steps):
                a_filters = a.get("args", {}).get("filters", {})
                e_filters = e.get("args", {}).get("filters", {})
                for key in e_filters:
                    total_filters += 1
                    if a_filters.get(key) == e_filters.get(key):
                        correct_filters += 1
            metrics["constraint_handling"] = correct_filters / total_filters if total_filters > 0 else 1.0

        return metrics
