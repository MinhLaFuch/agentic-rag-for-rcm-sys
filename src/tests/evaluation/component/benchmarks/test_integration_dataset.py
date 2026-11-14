"""Integration benchmark 6.5: dataset lint, presented-id/field metrics,
grounded_rate mode gating, and aggregation with missing keys."""

from __future__ import annotations

from pathlib import Path

import pytest

from package.evaluation.component._evaluator import ComponentEvaluator
from package.evaluation.component._loader import load_cases
from package.evaluation.component._schema import BenchmarkResult
from package.evaluation.component.benchmarks.integration_benchmark import (
    IntegrationBenchmark,
)
from package.evaluation.component.benchmarks.memory_correctness_setup import (
    create_test_interactions,
    create_test_mappings,
)

DATASET = (
    Path(__file__).parents[4]
    / "package" / "evaluation" / "component" / "benchmarks" / "integration_dataset.jsonl"
)

VG = "Video_Games::"


@pytest.fixture(scope="module")
def cases():
    return load_cases(DATASET)


@pytest.fixture(scope="module")
def fixture_ids():
    _, item2id, _ = create_test_mappings(create_test_interactions())
    return set(item2id)


@pytest.fixture(scope="module")
def evaluator():
    return IntegrationBenchmark()


def test_dataset_loads(cases):
    assert len(cases) == 13


def test_every_case_has_provenance(cases):
    for c in cases:
        assert c.metadata.get("expected_provenance"), c.case_id


def test_presented_ids_exist_in_fixture(cases, fixture_ids):
    bad = [
        (c.case_id, iid)
        for c in cases
        for iid in (c.expected.get("presented_item_ids") or [])
        if iid not in fixture_ids
    ]
    assert bad == [], f"presented ids not in fixture: {bad}"


def test_deterministic_cases_have_presented_ids(cases):
    """FilterTool/LookupTool chains are hand-computable; SimilarTool/SearchTool
    cases must carry structural provenance instead of fabricated id lists."""
    have = {c.case_id for c in cases if c.expected.get("presented_item_ids")}
    # int_013 contains SimilarTool but its ids are oracle-computed
    # (oracle_fixture_knn.py, cross-checked == real tools), not fabricated.
    assert have == {"int_001", "int_005", "int_008", "int_010", "int_012", "int_013"}


def test_grounded_rate_absent_in_template_mode(evaluator):
    actual = {
        "steps": [],
        "answer": {"status": "ok", "items": [], "grounded": True},
        "produced_item_ids": [],
        "produced_items": {},
    }
    m = evaluator.score_component(actual, {"expected_status": "ok"})
    assert "grounded_rate" not in m


def test_grounded_rate_emitted_in_llm_mode():
    ev = object.__new__(IntegrationBenchmark)
    ev.mode = "llm"
    actual = {
        "steps": [],
        "answer": {"status": "ok", "items": [], "grounded": True},
        "produced_item_ids": [],
        "produced_items": {},
    }
    m = ev.score_component(actual, {"expected_status": "ok"})
    assert m["grounded_rate"] == 1.0
    actual["answer"]["grounded"] = False
    assert ev.score_component(actual, {"expected_status": "ok"})["grounded_rate"] == 0.0


def _result(metrics: dict[str, float]) -> BenchmarkResult:
    return BenchmarkResult(
        case_id="x", actual_output=None, success=True, error=None,
        metrics=metrics, latency_seconds=0.0, token_usage=None,
    )


def test_aggregate_handles_missing_grounded_rate():
    """Template-mode results carry no grounded_rate; aggregation must not
    crash and must only average keys actually present."""
    results = [
        _result({"contract_valid": 1.0, "no_mismatch": 1.0}),
        _result({"contract_valid": 0.0, "no_mismatch": 1.0}),
        _result({"contract_valid": 1.0, "no_mismatch": 0.0,
                 "grounded_rate": 1.0}),
    ]
    agg = ComponentEvaluator._aggregate_metrics(None, results)
    assert agg["contract_valid_mean"] == pytest.approx(2 / 3)
    assert agg["grounded_rate_mean"] == 1.0  # mean over the one case that has it
    assert "grounded_rate_std" in agg


def test_presented_ids_exact_detects_drop_and_reorder(evaluator):
    row = {"item_id": VG + "vg_a", "price": 1.0}
    exp = {"presented_item_ids": [VG + "vg_a", VG + "vg_b"]}
    produced_items = {
        VG + "vg_a": row,
        VG + "vg_b": {"item_id": VG + "vg_b", "price": 150.0},
    }

    def actual(ids):
        return {
            "steps": [],
            "answer": {"status": "ok",
                       "items": [dict(produced_items[i]) for i in ids],
                       "grounded": True},
            "produced_item_ids": list(produced_items),
            "produced_items": produced_items,
        }

    assert evaluator.score_component(
        actual([VG + "vg_a", VG + "vg_b"]), exp)["presented_ids_exact"] == 1.0
    # dropped item
    assert evaluator.score_component(
        actual([VG + "vg_a"]), exp)["presented_ids_exact"] == 0.0
    # right ids, wrong order
    assert evaluator.score_component(
        actual([VG + "vg_b", VG + "vg_a"]), exp)["presented_ids_exact"] == 0.0


def test_item_fields_match_detects_field_mutation(evaluator):
    produced_items = {
        VG + "vg_a": {"item_id": VG + "vg_a", "price": 1.0, "title": "T"},
    }
    base = {
        "steps": [],
        "produced_item_ids": [VG + "vg_a"],
        "produced_items": produced_items,
    }
    good = dict(base, answer={"status": "ok", "items": [
        {"item_id": VG + "vg_a", "price": 1.0, "title": "T"}], "grounded": True})
    mutated = dict(base, answer={"status": "ok", "items": [
        {"item_id": VG + "vg_a", "price": 2.0, "title": "T"}], "grounded": True})
    dropped = dict(base, answer={"status": "ok", "items": [
        {"item_id": VG + "vg_a"}], "grounded": True})

    assert evaluator.score_component(good, {})["item_fields_match"] == 1.0
    assert evaluator.score_component(mutated, {})["item_fields_match"] == 0.0
    # dropped optional field is allowed only if produced row lacks it too —
    # here produced has price/title, so omitting them must NOT pass silently:
    # comparison covers fields present in either side.
    assert evaluator.score_component(dropped, {})["item_fields_match"] == 0.0


def test_real_tools_pass_all_cases(cases, evaluator):
    """Every case must satisfy contract_valid/no_mismatch plus the asserted
    metrics (presented_ids_exact, item_fields_match where present)."""
    bad = []
    for c in cases:
        m = evaluator.score_component(evaluator.run_component(c.input), c.expected)
        fails = {k: m[k] for k in ("contract_valid", "no_mismatch",
                                   "presented_ids_exact", "item_fields_match")
                 if k in m and m[k] != 1.0}
        if fails:
            bad.append((c.case_id, fails))
    assert bad == [], f"cases not at 1.0: {bad}"
