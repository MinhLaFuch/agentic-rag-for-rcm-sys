"""Executor benchmark: real execution of PlanExecutor._execute over fixture tools.

Scope (D1 option 1): this benchmark measures the execution engine only —
step execution, $N.path reference resolution, per-step error_kind reporting,
and empty/edge tool outputs — using REAL tools (FilterTool, SimilarTool,
LookupTool, SearchTool, RankTool) over the synthetic fixture corpus.

It deliberately does NOT exercise plan() or reflection: those need an LLM
provider and are covered by the planner benchmark (real LLM) and by
tests/agents/test_plan_reflect.py + test_executor_error_taxonomy.py
(ScriptedLLM + fake tools, fault injection).

Infra-failure scenarios from the retired dataset (timeout, rate limit,
network, auth, schema, ...) are NOT benchmark cases: PlanExecutor treats
tool-level failures uniformly, so they live in unit tests instead.
"""

from __future__ import annotations

import time
from typing import Any

from package.agents import PlanExecutor, build_tools
from package.evaluation.component._evaluator import ComponentEvaluator
from package.recommenders import ItemKNNRecommender
from package.tools import BaselineScorer

from .fixtures.create_test_corpus import create_test_corpus
from .fixtures.create_test_interactions import create_test_interactions
from .fixtures.create_test_mappings import create_test_mappings


class ExecutorBenchmark(ComponentEvaluator):
    """Evaluator for PlanExecutor step execution (no planning, no reflection)."""

    component_name = "executor"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

        # Real tools over the synthetic fixture corpus (same fixtures as planner/memory benchmarks)
        interactions = create_test_interactions()
        user2id, item2id, _ = create_test_mappings(interactions)
        corpus = create_test_corpus()
        knn = ItemKNNRecommender(10).fit(interactions[["user_idx", "item_idx"]])
        agent_tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus)
        self.item2id = item2id

        # llm=None is intentional: _execute never calls the LLM. PlanExecutor
        # stores it but only plan()/run() reflection paths use it.
        self.executor = PlanExecutor(llm=None, tools=agent_tools.for_planner(), reflect_rounds=0)

    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Execute the case's steps with real tools and return per-step results."""
        steps = case_input.get("steps", [])
        user_request = case_input.get("user_request", "")

        started = time.perf_counter()
        results = self.executor._execute(steps, user_request)
        latency = time.perf_counter() - started

        return {
            "steps": results,
            "latency_seconds": latency,
            "evidence_kind": "real_execution",
        }

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score execution results against expected per-step error kinds."""
        results = actual_output.get("steps", [])
        exp_all_ok = expected.get("all_steps_ok", True)
        exp_kinds = expected.get("step_error_kinds", [])
        exp_bad_refs = expected.get("bad_reference_count", 0)

        n = len(results)
        ok_count = sum(1 for r in results if r.get("ok"))
        bad_refs = sum(1 for r in results if r.get("error_kind") == "bad_reference")

        # Per-step error_kind accuracy: missing expectation means the step must succeed (error_kind None)
        kind_matches = 0
        for i, r in enumerate(results):
            exp_kind = exp_kinds[i] if i < len(exp_kinds) else None
            if r.get("error_kind") == exp_kind:
                kind_matches += 1
        # Steps expected to fail but absent from results count as mismatches
        expected_failures = sum(1 for k in exp_kinds if k is not None)
        kind_accuracy = kind_matches / max(n, expected_failures) if (n or expected_failures) else 1.0

        metrics = {
            "all_steps_ok": 1.0 if (ok_count == n) == exp_all_ok else 0.0,
            "step_success_rate": ok_count / n if n else 1.0,
            "error_kind_accuracy": kind_accuracy,
            "reference_resolution_ok": 1.0 if bad_refs == exp_bad_refs else 0.0,
        }

        # Step-count assertion: catches phantom/missing steps. exec_018
        # (steps=[]) relies on this — without it every implementation
        # scores 1.0 on the empty plan.
        exp_num_steps = expected.get("num_steps")
        if exp_num_steps is not None:
            metrics["step_count_match"] = 1.0 if n == exp_num_steps else 0.0

        # Data assertions: expected.step_outputs[i] describes what step i
        # must return (item ids ordered/unordered, counts, missing/unknown
        # ids, title keyword, fixture membership). Only hand-computable
        # expectations are asserted — SimilarTool kNN order and SearchTool
        # FTS ranking are NOT derivable from the fixture by hand.
        step_outputs = expected.get("step_outputs") or []
        checks = [self._check_step_output(results[i] if i < n else None, spec)
                  for i, spec in enumerate(step_outputs) if not spec.get("skip")]
        if checks:
            metrics["data_correctness"] = sum(checks) / len(checks)
        return metrics

    # Item-row keys produced by tools, in preference order
    _ITEM_ROW_KEYS = ("items", "candidates", "ranked")

    def _step_item_rows(self, step_result: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not step_result or not step_result.get("ok"):
            return []
        data = step_result.get("data") or {}
        for key in self._ITEM_ROW_KEYS:
            rows = data.get(key)
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
        return []

    def _step_item_ids(self, step_result: dict[str, Any] | None) -> list[str]:
        return [r["item_id"] for r in self._step_item_rows(step_result)
                if isinstance(r.get("item_id"), str)]

    def _check_step_output(self, step_result: dict[str, Any] | None, spec: dict[str, Any]) -> float:
        """1.0 iff every assertion in spec holds for this step's output."""
        ok = True
        data = (step_result or {}).get("data") or {}
        ids = self._step_item_ids(step_result)

        if "item_ids" in spec:
            want = spec["item_ids"]
            ok &= ids == want if spec.get("ordered", False) else set(ids) == set(want)
        if "item_count" in spec:
            ok &= len(ids) == spec["item_count"]
        if "missing_item_ids" in spec:
            ok &= set(data.get("missing_item_ids") or []) == set(spec["missing_item_ids"])
        if "unknown_items" in spec:
            ok &= set(data.get("unknown_items") or []) == set(spec["unknown_items"])
        if "total_matches" in spec:
            ok &= data.get("total_matches") == spec["total_matches"]
        if spec.get("fixture_ids_only"):
            valid = set(self.item2id)
            ok &= all(i in valid for i in ids)
        if "title_contains" in spec:
            needle = spec["title_contains"].lower()
            ok &= all(
                needle in str(r.get("title") or "").lower()
                for r in self._step_item_rows(step_result)
            )
        return 1.0 if ok else 0.0
