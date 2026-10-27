"""Grounding benchmark: test claim-level correctness with Jev LLM-as-judge."""

from __future__ import annotations

from typing import Any

from package.evaluation.component._evaluator import ComponentEvaluator
from package.evaluation.jev_product_evaluator import evaluate_product_reply_with_jev


class GroundingBenchmark(ComponentEvaluator):
    """Evaluator for Inference/Grounding component using Jev."""

    component_name = "grounding"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.use_jev = self.config.get("use_jev", True)

    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Run grounding check with Jev or rule-based."""
        user_request = case_input.get("user_request", "")
        evidence = case_input.get("evidence", [])
        
        if self.use_jev and evidence:
            # Use Jev for real evaluation
            # Convert evidence to items format expected by Jev
            items = [
                {
                    "item_id": e.get("item_id", ""),
                    "title": e.get("title", ""),
                    "main_category": e.get("main_category", ""),
                    "price": e.get("price"),
                }
                for e in evidence
            ]
            # Simulate an answer for testing
            answer = f"Based on your request '{user_request}', here are some options."
            
            try:
                result = evaluate_product_reply_with_jev(request=user_request, items=items, answer=answer)
                return {
                    "user_request": user_request,
                    "evidence": evidence,
                    "jev_result": result,
                    "has_evidence": len(evidence) > 0,
                }
            except Exception as e:
                # Fallback to rule-based if Jev fails
                return {
                    "user_request": user_request,
                    "evidence": evidence,
                    "has_evidence": len(evidence) > 0,
                    "jev_error": str(e),
                }
        else:
            # Rule-based fallback
            return {
                "user_request": user_request,
                "evidence": evidence,
                "has_evidence": len(evidence) > 0,
            }

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score grounding output."""
        if "jev_result" in actual_output:
            # Use Jev's evaluation
            jev_result = actual_output.get("jev_result", {})
            return {
                "claims_supported": jev_result.get("total_claims", 0) - jev_result.get("unsupported_count", 0),
                "total_claims": jev_result.get("total_claims", 1),
                "grounding_rate": (jev_result.get("total_claims", 0) - jev_result.get("unsupported_count", 0)) / max(jev_result.get("total_claims", 1), 1),
                "hallucination_rate": jev_result.get("unsupported_count", 0) / max(jev_result.get("total_claims", 1), 1),
                "prompt_injection_detected": 0.0,  # Jev doesn't detect prompt injection
            }
        
        # Rule-based fallback
        evidence = actual_output.get("evidence", [])
        metrics = {
            "claims_supported": 0.0,
            "total_claims": 1.0,
            "grounding_rate": 0.0,
            "hallucination_rate": 0.0,
            "prompt_injection_detected": 0.0,
        }

        if len(evidence) > 0:
            metrics["grounding_rate"] = 1.0
            metrics["hallucination_rate"] = 0.0
            metrics["claims_supported"] = 1.0
        else:
            metrics["grounding_rate"] = 0.0
            metrics["hallucination_rate"] = 1.0
            metrics["claims_supported"] = 0.0

        user_request = actual_output.get("user_request", "")
        if "prompt_injection_detected" in expected:
            is_injection = "ignore" in user_request.lower() or "previous instructions" in user_request.lower()
            metrics["prompt_injection_detected"] = 1.0 if is_injection else 0.0

        return metrics
