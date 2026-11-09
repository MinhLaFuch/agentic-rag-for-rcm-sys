"""Grounding benchmark: test claim-level correctness with Jev LLM-as-judge.

Evidence comes from the case dataset (synthetic fixture data); the judged
answer is the REAL inference output — AgentOutcome → compose_answer (template
mode by default, "llm" via config when provider credentials exist). The
pipeline upstream of the answer (planner/tools) is NOT exercised here — that
boundary is covered by the integration benchmark.
Judge failures (provider_error) fail the case; partial judge errors are reported
via judge_error_count and never counted as unsupported claims.
"""

from __future__ import annotations

import math
from typing import Any

from package.evaluation.component._evaluator import ComponentEvaluator
from package.evaluation.product_reply.evaluate_product_reply_with_jev import evaluate_product_reply_with_jev
from package.inference import ITEM_FIELDS

# Expected keys the dataset may assert; score_component turns them into label_agreement.
# total_claims is deliberately NOT assertable: it is produced by _extract_claims,
# code inside the measurement pipeline, so a label on it would be self-referential.
EXPECTED_METRIC_KEYS = ("claims_supported", "grounding_rate", "hallucination_rate")


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

        # Convert evidence to items format expected by Jev — ALL ITEM_FIELDS,
        # otherwise claims about rating/store/domain are unverifiable and a
        # faithful answer gets scored as unsupported.
        items = [{f: e.get(f) for f in ITEM_FIELDS} for e in evidence]
        # Phase 4.3: the judged answer is the REAL inference output —
        # AgentOutcome built from the evidence items → compose_answer —
        # not hand-written sentences. Template mode is deterministic and
        # needs no LLM; config mode="llm" uses the real provider when
        # credentials exist (compose_answer falls back to template otherwise).
        from package.inference import AgentOutcome, compose_answer

        mode = self.config.get("mode", "template")
        llm = None
        if mode == "llm":
            from package.api import build_llm_provider
            from package.config import load_config

            llm = build_llm_provider(load_config("agent/llm"))

        outcome = AgentOutcome(request_text=user_request, items=[dict(e) for e in evidence])
        composed = compose_answer(outcome, llm, mode=mode)
        answer = composed.text
        if not answer.strip():
            raise RuntimeError(f"compose_answer produced empty text (status={composed.status})")

        result = evaluate_product_reply_with_jev(request=user_request, items=items, answer=answer)

        if result.get("evaluation_state") == "provider_error":
            raise RuntimeError(f"Jev grounding evaluation failed: {result.get('summary')}")

        return {
            "user_request": user_request,
            "evidence": evidence,
            "jev_result": result,
            "has_evidence": True,
            "evidence_kind": "real_inference_output",
            "answer_composer": composed.composer,
            "answer_mode": mode,
            "answer_status": composed.status,
            # template mode prints evidence fields verbatim: it cannot produce an
            # unsupported claim, so hallucination is only measurable in llm mode.
            "measurement_scope": (
                "measures composer faithfulness incl. LLM hallucination"
                if mode == "llm"
                else "does not measure hallucination (answer_mode=template)"
            ),
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
            }

        supported = float(jev_result.get("supported_count", 0))
        unsupported = float(jev_result.get("unsupported_count", 0))
        judge_errors = float(jev_result.get("judge_error_count", 0))
        judged = supported + unsupported

        metrics = {
            "claims_supported": supported,
            "unsupported_count": unsupported,
            "judge_error_count": judge_errors,
            "total_claims": supported + unsupported + judge_errors,
            "grounding_rate": supported / judged if judged > 0 else 0.0,
            "hallucination_rate": unsupported / judged if judged > 0 else 0.0,
        }

        # Dataset labels are assertions, not decoration: every expected key the
        # case specifies must match the Jev-derived metric. Cases without any
        # expected key are excluded from label_agreement (the key is absent, so
        # aggregation only averages cases that were actually checked).
        checks = {
            k: float(expected[k])
            for k in EXPECTED_METRIC_KEYS
            if k in (expected or {})
        }
        if checks:
            matched = sum(
                1 for k, v in checks.items()
                if math.isclose(metrics[k], v, rel_tol=0.0, abs_tol=1e-9)
            )
            metrics["label_agreement"] = matched / len(checks)
        return metrics
