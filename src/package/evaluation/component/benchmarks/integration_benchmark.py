"""Integration tests for component boundaries."""

from __future__ import annotations

from typing import Any

from package.evaluation.component._evaluator import ComponentEvaluator


class IntegrationBenchmark(ComponentEvaluator):
    """Evaluator for integration between components."""

    component_name = "integration"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.boundary = self.config.get("boundary", "planner_executor")  # planner_executor, executor_inference, memory_planner

    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Run integration test for specific boundary."""
        boundary = case_input.get("boundary", self.boundary)
        
        if boundary == "planner_executor":
            return self._test_planner_executor(case_input)
        elif boundary == "executor_inference":
            return self._test_executor_inference(case_input)
        elif boundary == "memory_planner":
            return self._test_memory_planner(case_input)
        else:
            return {"error": f"Unknown boundary: {boundary}"}

    def _test_planner_executor(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Test Planner → Executor boundary."""
        plan = case_input.get("plan", [])
        expected_tools = case_input.get("expected_tools", [])
        
        # Check if plan references are valid
        valid_refs = True
        for step in plan:
            tool = step.get("tool")
            args = step.get("args", {})
            
            # Check if tool exists
            if tool not in expected_tools:
                valid_refs = False
                break
            
            # Check if references are valid
            for arg_value in args.values():
                if isinstance(arg_value, str) and arg_value.startswith("$"):
                    # Simple reference validation: $N.path
                    parts = arg_value.split(".")
                    if not parts[0].startswith("$") or not parts[0][1:].isdigit():
                        valid_refs = False
                        break
        
        return {
            "boundary": "planner_executor",
            "plan_valid": valid_refs,
            "plan": plan,
            "expected_tools": expected_tools,
        }

    def _test_executor_inference(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Test Executor → Inference boundary."""
        executor_output = case_input.get("executor_output", {})
        expected_fields = case_input.get("expected_fields", [])
        
        # Check if executor output has expected fields
        has_expected_fields = all(field in executor_output for field in expected_fields)
        
        return {
            "boundary": "executor_inference",
            "output_valid": has_expected_fields,
            "executor_output": executor_output,
            "expected_fields": expected_fields,
        }

    def _test_memory_planner(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Test Memory → Planner boundary."""
        memory_profile = case_input.get("memory_profile", {})
        planner_args = case_input.get("planner_args", {})
        
        # Check if planner args use memory profile correctly
        uses_memory = False
        for arg_value in planner_args.values():
            if isinstance(arg_value, dict):
                for key in memory_profile.keys():
                    if key in arg_value:
                        uses_memory = True
                        break
        
        return {
            "boundary": "memory_planner",
            "uses_memory": uses_memory,
            "memory_profile": memory_profile,
            "planner_args": planner_args,
        }

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score integration test."""
        boundary = actual_output.get("boundary", self.boundary)
        
        metrics = {
            "contract_valid": 0.0,
            "no_mismatch": 0.0,
        }
        
        if boundary == "planner_executor":
            metrics["contract_valid"] = 1.0 if actual_output.get("plan_valid") else 0.0
            metrics["no_mismatch"] = 1.0 if actual_output.get("plan_valid") else 0.0
        elif boundary == "executor_inference":
            metrics["contract_valid"] = 1.0 if actual_output.get("output_valid") else 0.0
            metrics["no_mismatch"] = 1.0 if actual_output.get("output_valid") else 0.0
        elif boundary == "memory_planner":
            expected_use = expected.get("expected_use", True)
            actual_use = actual_output.get("uses_memory", False)
            metrics["contract_valid"] = 1.0 if actual_use == expected_use else 0.0
            metrics["no_mismatch"] = 1.0 if actual_use == expected_use else 0.0
        
        return metrics
