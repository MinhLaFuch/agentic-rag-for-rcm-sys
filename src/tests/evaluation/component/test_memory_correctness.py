"""Tests for the MemoryTool correctness benchmark (oracle, dataset, leakage detector)."""

from __future__ import annotations

import pytest

from package.evaluation.component._loader import load_cases
from package.evaluation.component.benchmarks import build_memory_correctness_dataset as builder
from package.evaluation.component.benchmarks.memory_correctness_evaluator import MemoryCorrectnessEvaluator
from package.evaluation.component.benchmarks.memory_correctness_setup import (
    create_test_interactions, create_test_mappings, create_test_meta,
)
from package.evaluation.component.benchmarks.memory_oracle import DEFAULT_RECENT_N, compute_memory_oracle
from package.memory.memory_tool import MEMORY_RECENT_ITEMS, MemoryTool


@pytest.fixture(scope="module")
def world():
    inter = create_test_interactions()
    user2id, item2id, _ = create_test_mappings(inter)
    return inter, user2id, item2id, create_test_meta()


def _oracle(world, uid, top_n=5, as_of=None):
    inter, user2id, item2id, meta = world
    return compute_memory_oracle(inter, uid, user2id, item2id, meta, top_n, as_of)


def test_fixture_item_idx_consistent_with_item2id(world):
    """Regression: outlier row used item_idx=20 while item2id said 12 -> item silently dropped."""
    inter, _, item2id, _ = world
    for r in inter.itertuples():
        assert item2id[r.item_id] == r.item_idx


def test_oracle_matches_hand_computed_literals(world):
    """Expected values below are worked out by hand from the fixture, NOT produced by any code."""
    assert _oracle(world, "u_short", 2) == {
        "user_id": "u_short", "known": True, "n_interactions": 2,
        "top_categories": ["Action", "Puzzle"], "price_range": {"min": 1.0, "max": 150.0},
        "recent_items": ["Video_Games::vg_b", "Video_Games::vg_a"]}
    assert _oracle(world, "u_outlier_price", 2)["price_range"] == {"min": 1.0, "max": 1000.0}
    assert _oracle(world, "u_equal_prices", 2)["price_range"] == {"min": 1.0, "max": 1.0}
    assert _oracle(world, "u_null_prices", 2)["price_range"] is None
    # u_dup_items: vg_b (Puzzle) twice + vg_a (Action) once -> distinct-item tie, alphabetical -> Action
    dup = _oracle(world, "u_dup_items", 1)
    assert dup["top_categories"] == ["Action"] and dup["n_interactions"] == 3
    # cutoff is inclusive: ts<=4 of u_leakage_test keeps items a..e only
    cut = _oracle(world, "u_leakage_test", 3, as_of=4)
    assert cut["n_interactions"] == 5
    assert cut["recent_items"][0] == "Video_Games::vg_e"
    assert _oracle(world, "u_leakage_test", 3, as_of=-1)["known"] is False


def test_oracle_recent_n_matches_tool_config():
    assert DEFAULT_RECENT_N == MEMORY_RECENT_ITEMS


def test_oracle_does_not_depend_on_tool_or_corpus():
    import ast
    import package.evaluation.component.benchmarks.memory_oracle as mod
    tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m.startswith(("package.memory", "package.tools")) for m in imported)
    assert not any(isinstance(n, ast.Attribute) and n.attr == "select" for n in ast.walk(tree))


def test_committed_dataset_matches_oracle():
    assert builder.DATASET_PATH.read_text(encoding="utf-8") == builder.render(), \
        "run: python -m package.evaluation.component.benchmarks.build_memory_correctness_dataset"


def _evaluator(world, **kw):
    inter, user2id, item2id, meta = world
    return MemoryCorrectnessEvaluator(inter, user2id, item2id, meta, **kw)


def test_real_tool_passes_every_case(world):
    cases = load_cases(builder.DATASET_PATH)
    summary = _evaluator(world).run_benchmark(cases, component_name="memory_correctness")
    bad = [r.case_id for r in summary.per_case_results if r.metrics.get("all_fields_match") != 1.0]
    assert bad == []
    assert summary.metrics["future_leakage_mean"] == 0.0
    assert summary.metrics["success_rate"] == 1.0


def test_leakage_guard_cases_present_and_raising(world):
    cases = {c.case_id: c for c in load_cases(builder.DATASET_PATH)}
    ev = _evaluator(world)
    assert ev.run_component(cases["correctness_015"].input)["error_type"] == "LeakageError"
    assert "error_type" not in ev.run_component(cases["correctness_016"].input)


class _LeakyTool(MemoryTool):
    """Planted bug: ignores the snapshot cut. The detector MUST flag it."""

    def __init__(self, interactions, user2id, item2id, corpus, logger=None, as_of_timestamp=None):
        super().__init__(interactions, user2id, item2id, corpus, logger, as_of_timestamp=None)


def test_detector_catches_planted_leakage(world):
    inter, user2id, item2id, meta = world
    # leaky tool receives the FULL frame although the case asks for as_of=4
    class FullFrame(_LeakyTool):
        def __init__(self, interactions, *a, **k):
            super().__init__(inter, *a, **k)

    cases = [c for c in load_cases(builder.DATASET_PATH) if "cutoff" in c.tags]
    summary = _evaluator(world, tool_factory=FullFrame).run_benchmark(cases, component_name="leaky")
    assert summary.metrics["future_leakage_max"] == 1.0
    by_id = {r.case_id: r for r in summary.per_case_results}
    assert by_id["correctness_007"].metrics["future_leakage"] == 1.0
    assert by_id["correctness_007"].metrics["all_fields_match"] == 0.0
    assert by_id["correctness_008"].metrics["future_leakage"] == 0.0  # cutoff == last ts: nothing to leak


def test_detector_flags_guard_that_stops_raising(world):
    class NoGuard(MemoryTool):
        def __init__(self, interactions, user2id, item2id, corpus, logger=None, as_of_timestamp=None):
            super().__init__(interactions, user2id, item2id, corpus, logger, as_of_timestamp=None)

    cases = [c for c in load_cases(builder.DATASET_PATH) if "leakage_guard" in c.tags and "negative" in c.tags]
    s = _evaluator(world, tool_factory=NoGuard).run_benchmark(cases, component_name="noguard")
    assert s.metrics["error_behavior_correct_mean"] == 0.0
