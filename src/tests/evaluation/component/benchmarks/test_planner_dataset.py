"""Dataset lint tests for the planner benchmark.

Two layers, both against REAL fixture tools (PlanExecutor llm=None, same as
the executor benchmark):

1. Static: every expected step must pass the same schema validation the
   benchmark's plan_validity metric uses (_step_error vs input_schema).
2. Execution: expected.steps are run through PlanExecutor._execute on the
   real toolset — no step may error and the final result must be non-empty
   (ask_user cases with steps=[] are exempt).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from package.agents import PlanExecutor, build_tools
from package.evaluation.component._loader import load_cases
from package.evaluation.component.benchmarks.planner_benchmark import (
    PlannerBenchmark,
    _step_error,
    create_test_corpus,
    create_test_interactions,
    create_test_mappings,
)
from package.recommenders import ItemKNNRecommender
from package.tools import BaselineScorer

DATASET = (
    Path(__file__).parents[4]
    / "package" / "evaluation" / "component" / "benchmarks" / "planner_dataset.jsonl"
)
BACKLOG = DATASET.with_name("planner_dataset_backlog.jsonl")


@pytest.fixture(scope="module")
def cases():
    return load_cases(DATASET)


@pytest.fixture(scope="module")
def executor():
    interactions = create_test_interactions()
    user2id, item2id, _ = create_test_mappings(interactions)
    corpus = create_test_corpus()
    knn = ItemKNNRecommender(10).fit(interactions[["user_idx", "item_idx"]])
    tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus).for_planner_memory()
    return PlanExecutor(llm=None, tools=tools, reflect_rounds=0)


def _has_content(obj) -> bool:
    if isinstance(obj, dict):
        return any(_has_content(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return any(_has_content(v) for v in obj)
    return bool(obj)


def test_dataset_nonempty(cases):
    assert len(cases) >= 25


def test_backlog_file_valid_and_marked():
    rows = [json.loads(l) for l in BACKLOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 6
    for r in rows:
        assert r["metadata"].get("backlog") is True
        assert r["metadata"].get("limitation")


def test_scored_ids_disjoint_from_backlog(cases):
    backlog_ids = {json.loads(l)["case_id"] for l in BACKLOG.read_text(encoding="utf-8").splitlines() if l.strip()}
    assert not ({c.case_id for c in cases} & backlog_ids)


def test_case_ids_unique(cases):
    ids = [c.case_id for c in cases]
    assert len(ids) == len(set(ids))


def test_requires_clarification_consistent(cases):
    for c in cases:
        flagged = bool(c.expected.get("requires_clarification"))
        if flagged:
            assert c.expected.get("question"), c.case_id
            assert c.expected.get("steps", []) == [], c.case_id
        else:
            assert "requires_clarification" not in c.expected or not c.expected["requires_clarification"]


def test_expected_steps_pass_schema_validation(cases, executor):
    tools_by_name = dict(executor.tools)  # PlanExecutor stores tools as {name: Tool}
    offenders = []
    for c in cases:
        for i, step in enumerate(c.expected.get("steps", []), 1):
            err = _step_error(step, i, tools_by_name)
            if err:
                offenders.append(f"{c.case_id} step{i}: {err}")
    assert offenders == [], "expected plans violate real tool schemas:\n" + "\n".join(offenders)


def test_expected_plans_execute_clean(cases, executor):
    """Run each expected plan on the real tools: every step ok, last result non-empty."""
    failures = []
    for c in cases:
        steps = c.expected.get("steps", [])
        if not steps:
            continue  # ask_user cases produce no plan to execute
        results = executor._execute(steps, c.input.get("user_request", ""))
        for r in results:
            if not r.get("ok"):
                failures.append(f"{c.case_id}: {r.get('tool')} failed: {r.get('error')} (kind={r.get('error_kind')})")
        last = results[-1] if results else {}
        if results and not _has_content(last.get("data") or {}):
            failures.append(f"{c.case_id}: final step returned empty data")
    assert failures == [], "expected plans do not execute on fixture tools:\n" + "\n".join(failures)


# ---------- score_component metric tests (offline, no LLM) ----------

def _bench(tools_by_name):
    b = PlannerBenchmark.__new__(PlannerBenchmark)
    b._tools_by_name = tools_by_name
    return b


def _tools_by_name(executor):
    return dict(executor.tools)


def test_plan_validity_mutation_unknown_tool_arg_ref(executor):
    """A plan with a fake tool, an undeclared arg, and a forward ref must score 0."""
    bench = _bench(_tools_by_name(executor))
    bad_plan = [
        {"tool": "FakeTool", "args": {}},
        {"tool": "FilterTool", "args": {"filters": {"categories_none": ["RPG"]}}},
        {"tool": "LookupTool", "args": {"item_ids": "$9.candidates.*.item_id"}},
    ]
    actual = {"steps": bad_plan, "question": None}
    expected = {"steps": [], "question": None}
    m = bench.score_component(actual, expected)
    assert m["plan_validity"] == 0.0
    assert m["step_validity_rate"] == 0.0


def test_plan_validity_partial(executor):
    """One bad step out of three -> step_validity_rate = 2/3, plan_validity = 0."""
    bench = _bench(_tools_by_name(executor))
    steps = [
        {"tool": "FilterTool", "args": {"filters": {"domain": "Video_Games"}, "limit": 5}},
        {"tool": "FilterTool", "args": {"sort_by": "price"}},
        {"tool": "LookupTool", "args": {"item_ids": ["Video_Games::vg_a"]}},
    ]
    m = bench.score_component({"steps": steps, "question": None}, {"steps": [], "question": None})
    assert m["step_validity_rate"] == pytest.approx(2 / 3)
    assert m["plan_validity"] == 0.0


def test_plan_validity_clean_plan(executor):
    bench = _bench(_tools_by_name(executor))
    steps = [
        {"tool": "FilterTool", "args": {"filters": {"domain": "Video_Games"}, "limit": 5}},
        {"tool": "LookupTool", "args": {"item_ids": "$1.candidates.*.item_id"}},
    ]
    m = bench.score_component({"steps": steps, "question": None}, {"steps": [], "question": None})
    assert m["plan_validity"] == 1.0
    assert m["step_validity_rate"] == 1.0


def test_clarification_precision_token_f1(executor):
    bench = _bench(_tools_by_name(executor))
    expected = {"steps": [], "question": "What type of games are you looking for?", "requires_clarification": True}
    # differently worded but same content -> high F1, not 0
    m = bench.score_component(
        {"steps": [], "question": "Which kind of games do you want?"}, expected
    )
    assert 0.0 < m["clarification_precision"] < 1.0
    assert m["clarification_recall"] == 1.0
    # exact match -> 1.0
    m2 = bench.score_component(
        {"steps": [], "question": "What type of games are you looking for?"}, expected
    )
    assert m2["clarification_precision"] == 1.0


def test_refusal_vs_unnecessary_clarification(executor):
    bench = _bench(_tools_by_name(executor))
    flagged = {"steps": [], "question": "q?", "requires_clarification": True}
    # guessed instead of asking -> refusal_to_guess = 0, key present
    m = bench.score_component({"steps": [{"tool": "FilterTool", "args": {}}], "question": None}, flagged)
    assert m["refusal_to_guess"] == 0.0
    assert "unnecessary_clarification_rate" not in m
    # asked properly -> 1.0
    m = bench.score_component({"steps": [], "question": "q?"}, flagged)
    assert m["refusal_to_guess"] == 1.0
    # unflagged case: asking anyway -> unnecessary_clarification_rate = 0, refusal absent
    m = bench.score_component({"steps": [], "question": "q?"}, {"steps": [], "question": None})
    assert m["unnecessary_clarification_rate"] == 0.0
    assert "refusal_to_guess" not in m
    # unflagged, no question -> 1.0
    m = bench.score_component({"steps": [], "question": None}, {"steps": [], "question": None})
    assert m["unnecessary_clarification_rate"] == 1.0
