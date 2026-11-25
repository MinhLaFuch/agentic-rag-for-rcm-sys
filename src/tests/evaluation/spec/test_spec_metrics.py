"""Unit tests for Phase-2 spec_* metric functions (pure, offline).

Uses hand-built ItemSpecView lookups — no corpus/DB needed.
"""

from __future__ import annotations

from package.evaluation.spec import (
    ItemSpecView,
    aggregate_spec_metrics,
    category_spec_metrics,
    exclusion_spec_metrics,
    paired_bootstrap_diff,
)


def _lookup(mapping):
    return lambda iid: mapping.get(iid)


HIT = ItemSpecView(coarse="Toys", ancestor="Games", has_categories=True,
                   categories=frozenset({"Toys", "Games", "Building Toys"}))
OTHER_CAT = ItemSpecView(coarse="Electronics", ancestor="Computers",
                         has_categories=True, categories=frozenset({"Electronics"}))
UNCAT = ItemSpecView(coarse=None, ancestor=None, has_categories=False,
                     categories=frozenset())


# ------------------------------------------------------- category metrics -- #


def test_category_precision_strict_lenient_hit():
    rec = ["a", "b", "c"] + ["x"] * 7  # 3 real + padding to k=10
    lookup = _lookup({"a": HIT, "b": OTHER_CAT, "c": UNCAT})
    m = category_spec_metrics(rec, lookup, gold_coarse="Toys", gold_ancestor="Games")
    # strict: only "a" hits -> 1/10 ; lenient: "a" + "c"(uncat) -> 2/10
    assert m["spec_precision@10"] == 0.1
    assert m["spec_precision@10_lenient"] == 0.2
    assert m["spec_hit@10"] == 1.0
    # ancestor: "a".ancestor == "Games" == gold_ancestor -> 1/10
    assert m["spec_precision_ancestor@10"] == 0.1
    assert m["spec_result_coverage"] == 1.0
    assert m["spec_n_recommended"] == 10.0


def test_category_empty_list_scores_zero_but_counts():
    m = category_spec_metrics([], _lookup({}), gold_coarse="Toys")
    assert m["spec_precision@10"] == 0.0
    assert m["spec_hit@10"] == 0.0
    assert m["spec_result_coverage"] == 0.0  # coverage exposes the empty list


def test_category_unknown_item_is_miss_not_crash():
    m = category_spec_metrics(["ghost"] * 10, _lookup({}), gold_coarse="Toys")
    assert m["spec_precision@10"] == 0.0
    assert m["spec_precision@10_lenient"] == 0.0  # unknown != uncategorized


def test_category_short_list_fixed_k_denominator():
    # 3 hits out of only 3 recommended -> 3/10, not 3/3 (fixed-k convention)
    m = category_spec_metrics(["a", "b", "c"], _lookup({"a": HIT, "b": HIT, "c": HIT}),
                              gold_coarse="Toys")
    assert m["spec_precision@10"] == 0.3


def test_category_none_gold_scores_zero():
    m = category_spec_metrics(["a"] * 10, _lookup({"a": HIT}), gold_coarse=None)
    assert m["spec_precision@10"] == 0.0


# -------------------------------------------------------- exclusion metrics -- #


def test_exclusion_item_id_violation():
    rec = ["ok1", "bad", "ok2"]
    lookup = _lookup({"ok1": HIT, "bad": OTHER_CAT, "ok2": HIT})
    m = exclusion_spec_metrics(rec, lookup, excluded_item_ids=["bad"],
                                excluded_categories=[])
    assert m["spec_violation_rate"] == 1.0
    assert m["spec_result_coverage"] == 1.0


def test_exclusion_category_violation():
    rec = ["x"]
    lookup = _lookup({"x": HIT})  # HIT.categories contains "Building Toys"
    m = exclusion_spec_metrics(rec, lookup, excluded_item_ids=[],
                                excluded_categories=["Building Toys"])
    assert m["spec_violation_rate"] == 1.0


def test_exclusion_clean_and_empty():
    lookup = _lookup({"ok": OTHER_CAT})
    m = exclusion_spec_metrics(["ok"], lookup, ["bad"], ["Power Strips"])
    assert m["spec_violation_rate"] == 0.0
    # empty list: violation-free BUT coverage exposes it
    m2 = exclusion_spec_metrics([], lookup, ["bad"], [])
    assert m2["spec_violation_rate"] == 0.0
    assert m2["spec_result_coverage"] == 0.0


def test_exclusion_uncategorized_item_cannot_violate_via_category():
    # UNCAT has empty category set -> only item_id exclusion can catch it
    m = exclusion_spec_metrics(["u"], _lookup({"u": UNCAT}), [], ["Anything"])
    assert m["spec_violation_rate"] == 0.0


# ------------------------------------------------------------- aggregation -- #


def test_aggregate_and_bootstrap():
    rows = [{"spec_precision@10": 0.5}, {"spec_precision@10": 1.0}]
    agg = aggregate_spec_metrics(rows)
    assert agg["spec_precision@10"] == 0.75
    assert aggregate_spec_metrics([]) == {}

    ci = paired_bootstrap_diff([1.0, 0.0, 1.0], [0.0, 0.0, 0.0], n_boot=200)
    assert ci["diff"] == pytest.approx(2 / 3)
    assert ci["ci_low"] <= ci["diff"] <= ci["ci_high"]
    assert ci["n"] == 3.0


import pytest  # noqa: E402  (kept at bottom to keep header imports tidy)
