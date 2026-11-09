"""Executor benchmark 6.5: dataset lint + data/step-count metric tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from package.evaluation.component._loader import load_cases
from package.evaluation.component.benchmarks.executor_benchmark import ExecutorBenchmark
from package.evaluation.component.benchmarks.memory_correctness_setup import (
    create_test_interactions,
    create_test_mappings,
)

DATASET = (
    Path(__file__).parents[4]
    / "package" / "evaluation" / "component" / "benchmarks" / "executor_dataset.jsonl"
)


@pytest.fixture(scope="module")
def cases():
    return load_cases(DATASET)


@pytest.fixture(scope="module")
def fixture_ids():
    _, item2id, _ = create_test_mappings(create_test_interactions())
    return set(item2id)


@pytest.fixture(scope="module")
def evaluator():
    return ExecutorBenchmark()


def _ids_in_spec(spec: dict) -> list[str]:
    out = list(spec.get("item_ids") or [])
    out += spec.get("missing_item_ids") or []
    out += spec.get("unknown_items") or []
    return out


def test_dataset_loads(cases):
    assert len(cases) == 18


def test_every_case_has_num_steps_and_provenance(cases):
    for c in cases:
        assert "num_steps" in c.expected, c.case_id
        assert c.expected["num_steps"] == len(c.input["steps"]), c.case_id
        assert c.metadata.get("expected_provenance"), c.case_id


def test_step_output_ids_exist_in_fixture(cases, fixture_ids):
    bad = [
        (c.case_id, i, iid)
        for c in cases
        for i, spec in enumerate(c.expected.get("step_outputs") or [])
        for iid in _ids_in_spec(spec)
        if iid not in fixture_ids
    ]
    # exec_014/015/016 intentionally reference a nonexistent ghost id
    bad = [b for b in bad if "vg_zzz_ghost" not in b[2]]
    assert bad == [], f"expected ids not in fixture: {bad}"


def test_step_outputs_align_with_steps(cases):
    for c in cases:
        outs = c.expected.get("step_outputs") or []
        assert len(outs) <= len(c.input["steps"]), c.case_id


def test_data_correctness_detects_wrong_items(evaluator):
    exp = {"num_steps": 1, "step_outputs": [
        {"item_ids": ["Video_Games::vg_m"], "ordered": True}]}
    good = {"steps": [{"tool": "FilterTool", "ok": True, "args": {},
                       "data": {"candidates": [{"item_id": "Video_Games::vg_m"}]}}]}
    bad = {"steps": [{"tool": "FilterTool", "ok": True, "args": {},
                      "data": {"candidates": [{"item_id": "Video_Games::vg_a"}]}}]}
    assert evaluator.score_component(good, exp)["data_correctness"] == 1.0
    assert evaluator.score_component(bad, exp)["data_correctness"] == 0.0


def test_data_correctness_unordered_vs_ordered(evaluator):
    spec = {"item_ids": ["Video_Games::vg_a", "Video_Games::vg_b"]}
    rows = [{"item_id": "Video_Games::vg_a"}, {"item_id": "Video_Games::vg_b"}]
    rev = {"steps": [{"tool": "T", "ok": True, "args": {},
                      "data": {"candidates": list(reversed(rows))}}]}
    assert evaluator.score_component(rev, {"step_outputs": [spec]})["data_correctness"] == 1.0
    assert evaluator.score_component(
        rev, {"step_outputs": [dict(spec, ordered=True)]})["data_correctness"] == 0.0


def test_step_count_match_catches_phantom_step(evaluator):
    """exec_018 shape: empty plan must produce zero steps — a phantom step
    keeps every legacy metric at 1.0 but must fail step_count_match."""
    exp = {"all_steps_ok": True, "step_error_kinds": [], "bad_reference_count": 0,
           "num_steps": 0, "step_outputs": []}
    phantom = {"steps": [{"tool": "FilterTool", "ok": True, "args": {},
                          "data": {"candidates": []}, "error_kind": None}]}
    m = evaluator.score_component(phantom, exp)
    assert m["step_count_match"] == 0.0
    assert m["all_steps_ok"] == 1.0  # legacy metric alone would NOT catch it


CORRECTNESS_METRICS = (
    "all_steps_ok", "error_kind_accuracy", "reference_resolution_ok",
    "step_count_match", "data_correctness",
)


def test_real_tool_passes_all_cases(cases, evaluator):
    """Every correctness metric must be 1.0 (step_success_rate is a raw
    rate and legitimately <1.0 on expected-failure cases)."""
    bad = []
    for c in cases:
        m = evaluator.score_component(evaluator.run_component(c.input), c.expected)
        fails = {k: m[k] for k in CORRECTNESS_METRICS if k in m and m[k] != 1.0}
        if fails:
            bad.append((c.case_id, fails))
    assert bad == [], f"cases not at 1.0: {bad}"
