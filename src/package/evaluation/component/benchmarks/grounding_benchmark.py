"""Grounding benchmark: test claim-level correctness with Jev LLM-as-judge.

IMPORTANT — evidence_kind: the "answer" evaluated here is SYNTHETIC, generated
from the evidence fields themselves (see run_component). This benchmark measures
whether Jev judges evidence-derived claims as supported; it does NOT run the real
inference/grounding component. Real-output evaluation is planned for a later phase.
Judge failures (provider_error) fail the case; partial judge errors are reported
via judge_error_count and never counted as unsupported claims.
"""

from __future__ import annotations

from typing import Any

from package.evaluation.component._evaluator import ComponentEvaluator
from package.evaluation.product_reply.evaluate_product_reply_with_jev import evaluate_product_reply_with_jev


class GroundingBenchmark(ComponentEvaluator):
    """Evaluator for Inference/Grounding component using Jev."""

    component_name = "grounding"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.use_jev = self.config.get("use_jev", True)

    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Run grounding check with Jev.

        Raises on judge failure or missing evidence so the case is recorded as
        failed (success=False) instead of being scored by a fallback.
        """
        user_request = case_input.get("user_request", "")
        evidence = case_input.get("evidence", [])

        if not self.use_jev or not evidence:
            raise ValueError(
                "Grounding benchmark requires use_jev=true and non-empty evidence; "
                "there is nothing to ground otherwise."
            )

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
        # Generate a realistic answer for testing faithfulness evaluation
        # Use item titles and fields from evidence to produce actual claims
        item = evidence[0]
        answer_parts = []
        if item.get("title"):
            answer_parts.append(f"{item['title']} is a good choice.")
        if item.get("main_category"):
            answer_parts.append(f"It belongs to the {item['main_category']} category.")
        if item.get("price") is not None:
            answer_parts.append(f"The price is ${item['price']}.")
        if item.get("average_rating") is not None:
            answer_parts.append(f"It has a rating of {item['average_rating']}.")
        answer = " ".join(answer_parts)

        result = evaluate_product_reply_with_jev(request=user_request, items=items, answer=answer)

        if result.get("evaluation_state") == "provider_error":
            raise RuntimeError(f"Jev grounding evaluation failed: {result.get('summary')}")

        return {
            "user_request": user_request,
            "evidence": evidence,
            "jev_result": result,
            "has_evidence": True,
            "evidence_kind": "synthetic_answer_judge_only",
        }

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score grounding output from the Jev result only — no fallback scores."""
        jev_result = actual_output.get("jev_result")
        if not isinstance(jev_result, dict):
            return {
                "claims_supported": 0.0,
                "unsupported_count": 0.0,
                "judge_error_count": 0.0,
                "total_claims": 0.0,
                "grounding_rate": 0.0,
                "hallucination_rate": 0.0,
                "prompt_injection_detected": 0.0,
            }

        supported = float(jev_result.get("supported_count", 0))
        unsupported = float(jev_result.get("unsupported_count", 0))
        judge_errors = float(jev_result.get("judge_error_count", 0))
        judged = supported + unsupported

        user_request = actual_output.get("user_request", "")
        is_injection = "ignore" in user_request.lower() or "previous instructions" in user_request.lower()

        return {
            "claims_supported": supported,
            "unsupported_count": unsupported,
            "judge_error_count": judge_errors,
            "total_claims": supported + unsupported + judge_errors,
            "grounding_rate": supported / judged if judged > 0 else 0.0,
            "hallucination_rate": unsupported / judged if judged > 0 else 0.0,
            "prompt_injection_detected": 1.0 if is_injection else 0.0,
        }
