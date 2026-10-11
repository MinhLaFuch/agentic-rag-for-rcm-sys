"""Hardening tests for package/tools/ranking (ItemCFTool, RecoModelTool) and the scorer contract they rely on.

Fills the gaps left by test_tools_item_cf.py / test_tools_reco_model.py:
  1. mapping invariants: negative index and duplicate index in item2id
  2. wrongly typed inputs (exclude_input, exclude_seen, user_id, domain, items, top_k) -> ok=False, never raise
  3. note text must describe what the code really does
  4. scorer contract: one finite score per candidate, otherwise a clean error (never NaN in `ranked`)
  5. cold_start vs has_personal_signal are different things
  6. property: every candidate ends up in exactly one of ranked / excluded_seen / unscored_item_ids
"""

import math

import numpy as np
import pandas as pd
import pytest

from package.tools import BaselineScorer, ItemCFTool, RecoModelTool
from package.tools.base import ToolResult
from package.tools.recommenders import ItemKNNRecommender, PopularityRecommender
from tests.tools_helpers import EL_A, EL_D, VG_A, VG_B, VG_C


def _ids(result):
    return [c["item_id"] for c in result.data["candidates"]]


def _ranked_ids(result):
    return [r["item_id"] for r in result.data["ranked"]]


@pytest.fixture
def knn(cf_setup):
    interactions, _, _ = cf_setup
    return ItemKNNRecommender(5).fit(interactions)


@pytest.fixture
def cf_tool(knn, cf_setup, corpus):
    return ItemCFTool(knn, cf_setup[2], corpus=corpus)


@pytest.fixture
def reco_tool(knn, cf_setup, corpus):
    _, user2id, item2id = cf_setup
    return RecoModelTool(BaselineScorer(knn), user2id, item2id, corpus=corpus)


# ---------------------------------------------------------------------------------------------
# 1. mapping invariants
# ---------------------------------------------------------------------------------------------
def test_item_cf_negative_index_in_mapping_is_an_unknown_seed(knn, cf_setup, corpus):
    """-1 would silently select the LAST row of the similarity matrix (numpy negative indexing)."""
    _, _, item2id = cf_setup
    tool = ItemCFTool(knn, {**item2id, "Fake::neg": -1}, corpus=corpus)
    result = tool(items=["Fake::neg"])
    assert result.ok
    assert result.data["candidates"] == []
    assert result.data["unknown_items"] == ["Fake::neg"]


def test_item_cf_negative_seed_does_not_pollute_valid_seeds(knn, cf_setup, corpus):
    _, _, item2id = cf_setup
    tool = ItemCFTool(knn, {**item2id, "Fake::neg": -1}, corpus=corpus)
    mixed = tool(items=[VG_A, "Fake::neg"])
    clean = ItemCFTool(knn, item2id, corpus=corpus)(items=[VG_A])
    assert _ids(mixed) == _ids(clean)
    assert [c["similarity"] for c in mixed.data["candidates"]] == [c["similarity"] for c in clean.data["candidates"]]
    assert mixed.data["unknown_items"] == ["Fake::neg"]


def test_item_cf_seed_index_beyond_similarity_matrix_is_unknown(knn, cf_setup, corpus):
    _, _, item2id = cf_setup
    n = knn.similarity.shape[0]
    tool = ItemCFTool(knn, {**item2id, "Fake::big": n + 5}, corpus=corpus)
    result = tool(items=["Fake::big"])
    assert result.ok and result.data["candidates"] == [] and result.data["unknown_items"] == ["Fake::big"]


def test_item_cf_rejects_mapping_where_two_items_share_an_index(knn, cf_setup):
    """idx2item = {v: k} would silently drop one of the two items."""
    _, _, item2id = cf_setup
    broken = {**item2id, "Fake::dup": item2id[VG_A]}
    with pytest.raises(ValueError, match="(?i)duplicate|unique|same index"):
        ItemCFTool(knn, broken)


def test_reco_negative_index_in_mapping_goes_to_unscored(cf_setup, knn):
    """idx -1 passes `idx >= num_items` and would be 'scored' (as 0.0) and ranked."""
    _, user2id, item2id = cf_setup
    tool = RecoModelTool(BaselineScorer(knn), user2id, {**item2id, "Fake::neg": -1})
    result = tool(user_id="u3", candidates=[VG_B, "Fake::neg"])
    assert result.ok
    assert "Fake::neg" in result.data["unscored_item_ids"]
    assert "Fake::neg" not in _ranked_ids(result)
    assert VG_B in _ranked_ids(result)


# ---------------------------------------------------------------------------------------------
# 2. wrongly typed inputs: clean ok=False, never an exception
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["false", "true", "", 0, 1, None, [], [True]], ids=repr)
def test_item_cf_exclude_input_must_be_a_real_bool(cf_tool, value):
    result = cf_tool(items=[VG_A], exclude_input=value)  # must not raise
    assert isinstance(result, ToolResult)
    assert not result.ok and "exclude_input" in result.error


@pytest.mark.parametrize("value", [123, ["Electronics"], {"a": 1}, True], ids=repr)
def test_item_cf_domain_must_be_a_string(cf_tool, value):
    result = cf_tool(items=[VG_A], domain=value)
    assert not result.ok and "domain" in result.error


@pytest.mark.parametrize(
    "bad_items",
    [[VG_A, 5], [None], [["Video_Games::vg_a"]], [{"item_id": VG_A}], [""], "Video_Games::vg_a", 5, None],
    ids=repr,
)
def test_item_cf_items_must_be_a_list_of_non_empty_strings(cf_tool, bad_items):
    result = cf_tool(items=bad_items)  # must not raise (unhashable elements used to blow up in dict.fromkeys)
    assert not result.ok and "items" in result.error


@pytest.mark.parametrize("bad_top_k", ["5", True, 2.5, None, 0, -3, 10**6], ids=repr)
def test_item_cf_top_k_validation(cf_tool, bad_top_k):
    result = cf_tool(items=[VG_A], top_k=bad_top_k)
    assert not result.ok and "top_k" in result.error


@pytest.mark.parametrize("value", ["false", "true", "", 0, 1, None, [], [True]], ids=repr)
def test_reco_exclude_seen_must_be_a_real_bool(reco_tool, value):
    """'false' is truthy: a caller who thinks they switched the option off would still lose the seen items."""
    result = reco_tool(user_id="u2", candidates=[VG_A, EL_A], exclude_seen=value)
    assert not result.ok and "exclude_seen" in result.error


@pytest.mark.parametrize("bad_user", [["u1"], {"u": 1}, 123, None, "", "   "], ids=repr)
def test_reco_user_id_must_be_a_non_empty_string(reco_tool, bad_user):
    result = reco_tool(user_id=bad_user, candidates=[VG_A])  # must not raise (list is unhashable)
    assert not result.ok and "user_id" in result.error


@pytest.mark.parametrize("bad_top_k", ["3", True, 2.5, 0, -1, 10**6], ids=repr)
def test_reco_top_k_validation(reco_tool, bad_top_k):
    result = reco_tool(user_id="u1", candidates=[VG_B, EL_D], top_k=bad_top_k)
    assert not result.ok and "top_k" in result.error


@pytest.mark.parametrize("bad_candidates", [VG_A, 5, None, {"item_id": VG_A}, [VG_A, 5], [None], [["x"]]], ids=repr)
def test_reco_candidates_must_be_a_list_of_ids_or_dicts_with_item_id(reco_tool, bad_candidates):
    result = reco_tool(user_id="u1", candidates=bad_candidates)
    assert not result.ok and "candidates" in result.error


def test_reco_top_k_larger_than_candidates_returns_all(reco_tool):
    result = reco_tool(user_id="u1", candidates=[VG_B, EL_D], top_k=50)
    assert result.ok and len(result.data["ranked"]) == 2


def test_reco_duplicate_candidates_are_ranked_once(reco_tool):
    result = reco_tool(user_id="u3", candidates=[VG_B, VG_B, EL_A, VG_B])
    assert result.ok
    assert sorted(_ranked_ids(result)) == sorted([VG_B, EL_A])


# ---------------------------------------------------------------------------------------------
# 2b. ItemCFTool behaviour not covered elsewhere
# ---------------------------------------------------------------------------------------------
def test_item_cf_top_k_keeps_the_most_similar(cf_tool):
    assert _ids(cf_tool(items=[VG_A], top_k=1)) == [VG_B]


def test_item_cf_exclude_input_applies_to_every_seed(cf_tool):
    """EL_A is a neighbour of VG_A, but it is also a seed -> must be excluded; with the flag off it comes back."""
    excluded = cf_tool(items=[VG_A, EL_A], exclude_input=True)
    assert set(_ids(excluded)) == {VG_B, EL_D}
    kept = cf_tool(items=[VG_A, EL_A], exclude_input=False)
    assert {VG_A, EL_A} <= set(_ids(kept))


def test_item_cf_without_corpus_has_no_domain_key(knn, cf_setup):
    result = ItemCFTool(knn, cf_setup[2])(items=[VG_A])
    assert result.ok and all("domain" not in c for c in result.data["candidates"])


def test_item_cf_duplicate_seeds_count_once(cf_tool):
    once = cf_tool(items=[VG_A])
    twice = cf_tool(items=[VG_A, VG_A])
    assert [c["similarity"] for c in once.data["candidates"]] == [c["similarity"] for c in twice.data["candidates"]]


# ---------------------------------------------------------------------------------------------
# 3. note text must describe what the code does
# ---------------------------------------------------------------------------------------------
def test_item_cf_empty_domain_note_does_not_claim_filtering_after_top_k(cf_tool):
    """The domain filter runs BEFORE the top_k cut; the note must not say it happens 'after top-k'."""
    result = cf_tool(items=[EL_D], domain="Video_Games")  # EL_D's only neighbour is Electronics
    assert result.ok and result.data["candidates"] == []
    note = result.data["note"]
    assert note and "Video_Games" in note
    assert "after top-k" not in note


def test_item_cf_note_is_none_when_there_are_candidates(cf_tool):
    assert cf_tool(items=[VG_A]).data["note"] is None


# ---------------------------------------------------------------------------------------------
# 4. scorer contract: one finite score per candidate
# ---------------------------------------------------------------------------------------------
class FakeScorer:
    """Minimal CandidateScorer (the Protocol in package/tools/score) with a scriptable score()."""

    name = "FakeScorer"

    def __init__(self, score_fn, num_items=3, seen=(), known=True):
        self.score_fn, self.num_items, self._seen, self._known = score_fn, num_items, set(seen), known

    def is_known_user(self, user_idx):
        return self._known

    def seen_items(self, user_idx):
        return set(self._seen)

    def score(self, user_idx, item_idxs):
        return self.score_fn(np.asarray(item_idxs))

    def has_personal_signal(self, user_idx):
        return self._known


def _fake_tool(score_fn, **kw):
    return RecoModelTool(FakeScorer(score_fn, **kw), {"u": 0}, {"i0": 0, "i1": 1, "i2": 2})


def test_reco_with_a_well_behaved_scorer_sorts_descending_with_contiguous_ranks():
    tool = _fake_tool(lambda idx: np.array([0.1, 0.9, 0.5])[idx])
    result = tool(user_id="u", candidates=["i0", "i1", "i2"])
    assert _ranked_ids(result) == ["i1", "i2", "i0"]
    assert [r["rank"] for r in result.data["ranked"]] == [1, 2, 3]


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf], ids=["nan", "inf", "-inf"])
def test_reco_never_returns_a_non_finite_score(bad):
    tool = _fake_tool(lambda idx: np.where(idx == 1, bad, 0.5))
    result = tool(user_id="u", candidates=["i0", "i1", "i2"])
    if result.ok:  # either the item is dropped / reported, or the call fails cleanly -- never a NaN in `ranked`
        assert all(math.isfinite(r["score"]) for r in result.data["ranked"])
        assert "i1" not in _ranked_ids(result)
    else:
        assert "score" in result.error.lower()


@pytest.mark.parametrize("n_scores", [0, 2, 4], ids=["too_few_0", "too_few_2", "too_many_4"])
def test_reco_scorer_returning_wrong_number_of_scores_is_a_clean_error(n_scores):
    tool = _fake_tool(lambda idx: np.full(n_scores, 0.5))
    result = tool(user_id="u", candidates=["i0", "i1", "i2"])  # must not raise IndexError
    assert not result.ok and "score" in result.error.lower()


def test_baseline_scorer_rejects_unfitted_or_wrong_model():
    with pytest.raises(AttributeError, match="scores|user_items|num_items"):
        BaselineScorer(object())


# ---------------------------------------------------------------------------------------------
# 5. cold_start vs has_personal_signal
# ---------------------------------------------------------------------------------------------
def test_known_user_without_neighbours_is_not_cold_start_but_has_no_personal_signal():
    """a only touched X, and nobody else touched X -> the model knows a, but X has no similar items."""
    inter = pd.DataFrame({"user_id": ["a", "b", "b", "c", "c"], "item_id": ["X", "Y", "Z", "Y", "Z"]})
    user2id = {u: i for i, u in enumerate(inter["user_id"].unique())}
    item2id = {it: i for i, it in enumerate(inter["item_id"].unique())}
    inter["user_idx"] = inter["user_id"].map(user2id)
    inter["item_idx"] = inter["item_id"].map(item2id)
    tool = RecoModelTool(BaselineScorer(ItemKNNRecommender(5).fit(inter)), user2id, item2id)

    known_isolated = tool(user_id="a", candidates=["Y", "Z"])
    assert known_isolated.ok
    assert known_isolated.data["cold_start"] is False
    assert known_isolated.data["has_personal_signal"] is False

    with_signal = tool(user_id="b", candidates=["X", "Y"], exclude_seen=False)
    assert with_signal.data["cold_start"] is False and with_signal.data["has_personal_signal"] is True

    stranger = tool(user_id="nobody", candidates=["X", "Y"])
    assert stranger.data["cold_start"] is True and stranger.data["has_personal_signal"] is False


# ---------------------------------------------------------------------------------------------
# 6. property: every candidate lands in exactly one bucket
# ---------------------------------------------------------------------------------------------
ALL_CANDIDATES = [VG_A, VG_B, VG_C, EL_A, EL_D, "Video_Games::not_in_any_mapping"]


@pytest.mark.parametrize("user", ["u1", "u2", "u3", "u4", "u5", "u6", "u7", "u8", "u9", "u10", "u13", "brand_new_user"])
@pytest.mark.parametrize("exclude_seen", [True, False])
def test_reco_partitions_candidates_into_ranked_seen_and_unscored(reco_tool, user, exclude_seen):
    result = reco_tool(user_id=user, candidates=ALL_CANDIDATES, exclude_seen=exclude_seen)
    assert result.ok
    ranked, seen, unscored = _ranked_ids(result), result.data["excluded_seen"], result.data["unscored_item_ids"]
    buckets = ranked + seen + unscored
    assert sorted(buckets) == sorted(ALL_CANDIDATES), "a candidate was lost or duplicated"
    scores = [r["score"] for r in result.data["ranked"]]
    assert scores == sorted(scores, reverse=True)
    assert [r["rank"] for r in result.data["ranked"]] == list(range(1, len(ranked) + 1))
    if not exclude_seen:
        assert seen == []
    assert all(math.isfinite(s) for s in scores)
