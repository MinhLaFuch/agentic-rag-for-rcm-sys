"""Extra ranking-layer contract tests (the strict-validation matrix is in tests/tools/ranking/test_ranking_hardening.py)."""

import pytest

from package.tools import BaselineScorer, ItemCFTool, RecoModelTool
from package.tools.recommenders import ItemKNNRecommender, PopularityRecommender

G_A1, G_B2, G_C3, G_D4, T_A1, T_E5 = "Games::A1", "Games::B2", "Games::C3", "Games::D4", "Toys::A1", "Toys::E5"


@pytest.fixture
def knn(world):
    return ItemKNNRecommender(neighbors=5).fit(world.interactions)


@pytest.fixture
def cf_tool(knn, world):
    return ItemCFTool(knn, world.item2id, corpus=world.corpus)


@pytest.fixture
def reco_tool(knn, world):
    return RecoModelTool(BaselineScorer(knn), world.user2id, world.item2id, corpus=world.corpus)


def test_item_cf_ranks_by_hand_computed_similarity_with_index_tie_break(cf_tool):
    # cos(A1,.): B2 and T_A1 tie at 4/sqrt(20)=0.894 (lower index first), E5 3/sqrt(15)=0.775, C3 2/sqrt(10)=0.632, D4 1/sqrt(5)=0.447
    result = cf_tool(items=[G_A1])
    assert [c["item_id"] for c in result.data["candidates"]] == [G_B2, T_A1, T_E5, G_C3, G_D4]
    assert [round(c["similarity"], 3) for c in result.data["candidates"]] == [0.894, 0.894, 0.775, 0.632, 0.447]
    assert [c["domain"] for c in result.data["candidates"]] == ["Games", "Toys", "Toys", "Games", "Games"]
    assert G_A1 not in [c["item_id"] for c in result.data["candidates"]]  # seed excluded by default


def test_item_cf_domain_filter_runs_before_the_top_k_cut(cf_tool):
    result = cf_tool(items=[G_A1], domain="Toys", top_k=1)
    assert [c["item_id"] for c in result.data["candidates"]] == [T_A1]  # not "top-1 overall then filter"
    assert [c["item_id"] for c in cf_tool(items=[G_A1], domain="Toys").data["candidates"]] == [T_A1, T_E5]


def test_item_cf_unknown_domain_is_rejected_and_blank_domain_means_no_filter(cf_tool):
    assert not cf_tool(items=[G_A1], domain="Nowhere").ok
    assert len(cf_tool(items=[G_A1], domain="").data["candidates"]) == 5


def test_item_cf_same_asin_in_two_domains_are_different_seeds(cf_tool):
    a = [c["item_id"] for c in cf_tool(items=[G_A1], top_k=5).data["candidates"]]
    b = [c["item_id"] for c in cf_tool(items=[T_A1], top_k=5).data["candidates"]]
    assert T_A1 in a and G_A1 in b and a != b


def test_item_cf_unknown_seed_is_reported_not_fatal(cf_tool):
    result = cf_tool(items=["Games::ghost", G_B2])
    assert result.ok and result.data["unknown_items"] == ["Games::ghost"] and result.data["candidates"]


def test_reco_ranks_unseen_candidates_by_hand_computed_scores(reco_tool):
    # u2 saw {A1,B2,T_A1,T_E5}; unseen candidates C3 and D4 get sum of similarities to the history:
    # C3: .632+.707+.707+.816 = 2.867 (hand: 2/sqrt10 + 2/sqrt8 + 2/sqrt8 + 2/sqrt6)  D4: .447+.5+.5+.577
    result = reco_tool(user_id="u2", candidates=[G_B2, T_A1, T_E5, G_C3, G_D4])
    d = result.data
    assert [r["item_id"] for r in d["ranked"]] == [G_C3, G_D4]
    c3 = 2 / 10 ** 0.5 + 2 / 8 ** 0.5 + 2 / 8 ** 0.5 + 2 / 6 ** 0.5
    d4 = 1 / 5 ** 0.5 + 1 / 4 ** 0.5 + 1 / 4 ** 0.5 + 1 / 3 ** 0.5
    assert d["ranked"][0]["score"] == pytest.approx(c3, abs=1e-4) and d["ranked"][1]["score"] == pytest.approx(d4, abs=1e-4)
    assert d["excluded_seen"] == [G_B2, T_A1, T_E5] and d["cold_start"] is False and d["has_personal_signal"] is True
    assert [r["domain"] for r in d["ranked"]] == ["Games", "Games"]


def test_reco_cold_user_is_ranked_by_popularity_and_flagged(reco_tool):
    result = reco_tool(user_id="stranger", candidates=[G_D4, G_C3, T_E5, G_A1])
    assert [r["item_id"] for r in result.data["ranked"]] == [G_A1, T_E5, G_C3, G_D4]  # popularity 5,3,2,1
    assert result.data["cold_start"] is True and result.data["has_personal_signal"] is False


def test_reco_user_with_everything_seen_gets_an_explanatory_note(reco_tool):
    result = reco_tool(user_id="u5", candidates=[G_A1, G_B2])
    assert result.ok and result.data["ranked"] == [] and "seen" in result.data["note"]


def test_reco_never_returns_items_outside_the_candidate_set(reco_tool, world):
    candidates = [G_C3, T_A1, "Games::ghost"]
    ranked = reco_tool(user_id="u0", candidates=candidates, exclude_seen=False).data
    assert {r["item_id"] for r in ranked["ranked"]} <= set(candidates)
    assert ranked["unscored_item_ids"] == ["Games::ghost"]


def test_reco_ties_keep_candidate_input_order(world):
    # B2 and T_A1 have equal popularity (4): the order of the input decides, deterministically
    tool = RecoModelTool(BaselineScorer(PopularityRecommender().fit(world.interactions)), world.user2id, world.item2id)
    one = [r["item_id"] for r in tool(user_id="stranger", candidates=[G_B2, T_A1]).data["ranked"]]
    two = [r["item_id"] for r in tool(user_id="stranger", candidates=[T_A1, G_B2]).data["ranked"]]
    assert one == [G_B2, T_A1] and two == [T_A1, G_B2]


def test_reco_top_k_boundaries(reco_tool):
    cands = [G_A1, T_E5, G_C3]
    assert len(reco_tool(user_id="stranger", candidates=cands, top_k=1).data["ranked"]) == 1
    assert len(reco_tool(user_id="stranger", candidates=cands, top_k=3).data["ranked"]) == 3
    assert len(reco_tool(user_id="stranger", candidates=cands, top_k=999).data["ranked"]) == 3


def test_reco_output_keys_match_the_declared_output_schema(reco_tool):
    data = reco_tool(user_id="u1", candidates=[G_B2]).data
    assert set(data) == set(RecoModelTool.output_schema)
