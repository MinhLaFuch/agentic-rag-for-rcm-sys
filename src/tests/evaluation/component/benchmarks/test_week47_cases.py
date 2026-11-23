"""Week-47 benchmark cases: exec_019/020/021/023, planner_033-035, int_013.

Expected values were hand-computed from the fixtures (see each case's
metadata.expected_provenance); exec_021/int_013 additionally cross-checked
against scripts/eda_diagnostic/oracle_fixture_knn.py which reimplements the
KNN math without importing the recommender/tools under test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from package.evaluation.component._loader import load_cases
from package.evaluation.component.benchmarks.executor_benchmark import ExecutorBenchmark
from package.evaluation.component.benchmarks.integration_benchmark import IntegrationBenchmark

BENCH = (
    Path(__file__).parents[4]
    / "package" / "evaluation" / "component" / "benchmarks"
)


@pytest.fixture(scope="module")
def executor():
    return ExecutorBenchmark()


@pytest.fixture(scope="module")
def integration():
    return IntegrationBenchmark()  # template mode: deterministic, no LLM


def _run_score(evaluator, case):
    actual = evaluator.run_component(case.input)
    return evaluator.score_component(actual, case.expected), actual


# --- exec_019: $1.price_range.max -> MemoryTool price_range=None -> bad_reference

def test_exec_019_null_price_range_is_bad_reference(executor):
    case = next(c for c in load_cases(BENCH / "executor_dataset.jsonl") if c.case_id == "exec_019")
    metrics, actual = _run_score(executor, case)
    kinds = [s.get("error_kind") for s in actual["steps"]]
    assert kinds == [None, "bad_reference"]
    assert metrics["error_kind_accuracy"] == 1.0
    assert metrics["all_steps_ok"] == 1.0
    assert metrics["reference_resolution_ok"] == 1.0


# --- exec_020: SearchTool ok-on-empty (coverage, not a timeout regression)

def test_exec_020_search_no_match_returns_ok_empty(executor):
    case = next(c for c in load_cases(BENCH / "executor_dataset.jsonl") if c.case_id == "exec_020")
    metrics, actual = _run_score(executor, case)
    data = actual["steps"][0]["data"]
    assert actual["steps"][0]["ok"] is True
    assert data["candidates"] == []
    assert data["total_matches"] == 0
    assert metrics["data_correctness"] == 1.0


# --- exec_021: successful $1.candidates chain SimilarTool -> RankTool

def test_exec_021_similar_to_rank_chain(executor):
    case = next(c for c in load_cases(BENCH / "executor_dataset.jsonl") if c.case_id == "exec_021")
    metrics, actual = _run_score(executor, case)
    assert [s.get("error_kind") for s in actual["steps"]] == [None, None]
    # oracle_fixture_knn.py: similar(vg_a,5) = [vg_b,c,d,e,g]; u_short seen={vg_a,vg_b}
    # -> exclude_seen drops vg_b -> ranked [vg_c,vg_d,vg_e,vg_g]
    ranked_ids = [r["item_id"] for r in actual["steps"][1]["data"]["ranked"]]
    assert ranked_ids == [
        "Video_Games::vg_c", "Video_Games::vg_d",
        "Video_Games::vg_e", "Video_Games::vg_g",
    ]
    assert metrics["data_correctness"] == 1.0
    assert metrics["error_kind_accuracy"] == 1.0


# --- exec_023: empty-result success (price_max below fixture minimum)

def test_exec_023_empty_result_is_ok(executor):
    case = next(c for c in load_cases(BENCH / "executor_dataset.jsonl") if c.case_id == "exec_023")
    metrics, actual = _run_score(executor, case)
    step = actual["steps"][0]
    assert step["ok"] is True and step["error_kind"] is None
    assert step["data"]["candidates"] == []
    assert step["data"]["total_matches"] == 0
    assert metrics["data_correctness"] == 1.0


# --- planner_033/034/035: dataset-level expectations (planner needs LLM to run)

def test_planner_unanswerable_cases_declare_clarification():
    cases = {c.case_id: c for c in load_cases(BENCH / "planner_dataset.jsonl")}
    for cid in ("planner_033", "planner_034"):
        c = cases[cid]
        assert c.expected["steps"] == []
        assert c.expected.get("requires_clarification") is True
        assert c.expected.get("question")
    # planner_035 is the boundary counterpart: answerable-but-empty -> run the
    # tool, do NOT clarify.
    c = cases["planner_035"]
    assert c.expected["steps"] and c.expected["steps"][0]["tool"] == "FilterTool"
    assert c.expected.get("question") is None
    assert "requires_clarification" not in c.expected


# --- int_013: $ref chain end-to-end through compose_answer (template mode)

def test_int_013_presented_ids_match_oracle(integration):
    case = next(c for c in load_cases(BENCH / "integration_dataset.jsonl") if c.case_id == "int_013")
    metrics, actual = _run_score(integration, case)
    assert actual["answer"]["status"] == "ok"
    assert metrics["contract_valid"] == 1.0
    assert metrics["no_mismatch"] == 1.0
    assert metrics["presented_ids_exact"] == 1.0
