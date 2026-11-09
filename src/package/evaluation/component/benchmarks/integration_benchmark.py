"""Integration benchmark: real planner-executor → inference boundary.

Phase 4.2 rewrite. The old version validated dict fields already present in
the case input (self-referential — it tested fixture data, not the boundary).
This version runs the REAL chain on the fixture corpus:

    case steps → PlanExecutor._execute (real tools)
               → outcome_from_plan_results (AgentOutcome)
               → compose_answer (template mode by default; "llm" mode needs
                 LLM_BASE_URL/LLM_API_KEY and falls back to template otherwise)

Metrics:
- contract_valid: answer.status matches expected AND every presented item is
  a well-formed dict with a string item_id.
- no_mismatch: every item_id the answer presents was actually produced by an
  executed step (the inference stage may not invent items).
- grounded_rate: answer.grounded flag — ONLY emitted in mode="llm".
  compose_template hardcodes grounded=True, so in template mode the metric
  is a constant 1.0 that cannot fail; emitting it would imply a check that
  does not exist (same honesty rule as the grounding benchmark's
  measurement_scope).

Cases provide {user_request, steps} executed with real tools — same fixture
setup as the executor/planner benchmarks. evidence_kind=real_execution.
"""

from __future__ import annotations

import time
from typing import Any

from package.agents import PlanExecutor, build_tools
from package.evaluation.component._evaluator import ComponentEvaluator
from package.inference import ITEM_FIELDS, compose_answer, outcome_from_plan_results
from package.recommenders import ItemKNNRecommender
from package.tools import BaselineScorer

from .fixtures.create_test_corpus import create_test_corpus
from .fixtures.create_test_interactions import create_test_interactions
from .fixtures.create_test_mappings import create_test_mappings

# Keys in step `data` that carry item rows with item_id
_ITEM_ROW_KEYS = ("candidates", "items", "ranked")
# Item fields compared by item_fields_match (canonical inference field list)
_ITEM_FIELDS = ITEM_FIELDS


class IntegrationBenchmark(ComponentEvaluator):
    """Evaluator for the executor → inference boundary (real execution)."""

    component_name = "integration"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        # "template" is deterministic and needs no LLM; "llm" requires provider
        # credentials and compose_answer falls back to template without them.
        self.mode = self.config.get("mode", "template")
        self.llm = None
        if self.mode == "llm":
            from package.api import build_llm_provider
            from package.config import load_config

            self.llm = build_llm_provider(load_config("agent/llm"))

        interactions = create_test_interactions()
        user2id, item2id, _ = create_test_mappings(interactions)
        corpus = create_test_corpus()
        knn = ItemKNNRecommender(10).fit(interactions[["user_idx", "item_idx"]])
        agent_tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus)
        self.executor = PlanExecutor(llm=None, tools=agent_tools.for_planner(), reflect_rounds=0)

    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Execute steps for real, then run outcome → compose_answer."""
        steps = case_input.get("steps", [])
        user_request = case_input.get("user_request", "")

        started = time.perf_counter()
        results = self.executor._execute(steps, user_request)
        outcome = outcome_from_plan_results(user_request, results)
        answer = compose_answer(outcome, self.llm, mode=self.mode)
        latency = time.perf_counter() - started

        # Item ids AND rows actually produced by executed steps (ground
        # truth for no_mismatch / item_fields_match). Fields are merged
        # first-non-None across all rows for an id — the same merge
        # outcome_from_plan_results applies (LookupTool first, then others).
        produced_ids: set[str] = set()
        produced_items: dict[str, dict[str, Any]] = {}
        for r in results:
            if not r.get("ok"):
                continue
            for key in _ITEM_ROW_KEYS:
                for row in (r.get("data") or {}).get(key) or []:
                    if isinstance(row, dict) and isinstance(row.get("item_id"), str):
                        produced_ids.add(row["item_id"])
                        slot = produced_items.setdefault(row["item_id"], {})
                        for f, v in row.items():
                            if slot.get(f) is None and v is not None:
                                slot[f] = v

        return {
            "steps": results,
            "outcome": {
                "items": outcome.items,
                "errors": outcome.errors,
                "invented_ids": outcome.invented_ids,
                "n_steps": outcome.n_steps,
            },
            "answer": answer.to_dict(),
            "produced_item_ids": sorted(produced_ids),
            "produced_items": produced_items,
            "latency_seconds": latency,
            "evidence_kind": "real_execution",
        }

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        answer = actual_output.get("answer") or {}
        produced = set(actual_output.get("produced_item_ids") or [])
        presented = [i for i in (answer.get("items") or []) if isinstance(i, dict)]
        presented_ids = {i.get("item_id") for i in presented}

        exp_status = expected.get("expected_status")
        status_ok = answer.get("status") == exp_status if exp_status else True
        well_formed = all(isinstance(i.get("item_id"), str) and i.get("item_id") for i in presented)
        min_items = expected.get("min_items", 0)

        presented_ids_list = [i.get("item_id") for i in presented]
        exp_presented = expected.get("presented_item_ids")

        metrics = {
            # status matches expectation AND presented items are well-formed AND enough items
            "contract_valid": 1.0
            if status_ok and well_formed and len(presented) >= min_items
            else 0.0,
            # inference may only present items the executed steps actually produced
            "no_mismatch": 1.0 if presented_ids <= produced else 0.0,
        }

        # Ordered presented-id assertion (hand-computed fixture expectations;
        # only asserted where the chain is deterministic — FilterTool/LookupTool
        # cases, not SimilarTool kNN or SearchTool FTS order).
        if exp_presented is not None:
            metrics["presented_ids_exact"] = (
                1.0 if presented_ids_list == exp_presented else 0.0
            )

        # Field fidelity: every field the answer presents must equal the value
        # the executed steps actually produced for that item — catches a
        # composer that drops items' fields or rewrites values (e.g. price).
        produced_items = actual_output.get("produced_items") or {}
        if presented:
            field_ok = []
            for item in presented:
                iid = item.get("item_id")
                row = produced_items.get(iid) or {}
                field_ok.append(all(
                    item.get(f) == row.get(f)
                    for f in _ITEM_FIELDS
                    if f in row or item.get(f) is not None
                ))
            metrics["item_fields_match"] = sum(field_ok) / len(field_ok)

        # grounded is only meaningful in llm mode — template hardcodes True.
        if self.mode == "llm":
            metrics["grounded_rate"] = 1.0 if answer.get("grounded", False) else 0.0
        return metrics
