import pytest

from tools.recommenders.baselines import ItemKNNRecommender, PopularityRecommender
from src.tools import ItemCFTool
from tests.tools_helpers import EL_A, EL_D, VG_A, VG_B


def test_item_cf_returns_similar_items_with_similarity_and_domain(corpus, cf_setup):
    interactions, _, item2id = cf_setup
    tool = ItemCFTool(ItemKNNRecommender(5).fit(interactions), item2id, corpus=corpus)
    result = tool(items=[VG_A])
    assert result.ok
    candidates = result.data["candidates"]
    assert VG_A not in {c["item_id"] for c in candidates}  # input excluded
    assert [c["item_id"] for c in candidates] == [VG_B, EL_A]  # co-purchased, sorted by similarity
    assert candidates[0]["similarity"] >= candidates[1]["similarity"] > 0
    assert candidates[1]["domain"] == "Electronics"  # cross-domain by default


def test_item_cf_domain_filter_and_keep_input(corpus, cf_setup):
    interactions, _, item2id = cf_setup
    tool = ItemCFTool(ItemKNNRecommender(5).fit(interactions), item2id, corpus=corpus)
    only_electronics = tool(items=[VG_A], domain="Electronics").data["candidates"]
    assert [c["item_id"] for c in only_electronics] == [EL_A]
    assert VG_B in {c["item_id"] for c in tool(items=[VG_A]).data["candidates"]}
    assert EL_A not in {c["item_id"] for c in tool(items=[EL_A], exclude_input=True).data["candidates"]}


def test_item_cf_sums_similarity_over_multiple_seeds(corpus, cf_setup):
    interactions, _, item2id = cf_setup
    tool = ItemCFTool(ItemKNNRecommender(5).fit(interactions), item2id, corpus=corpus)
    single = {c["item_id"]: c["similarity"] for c in tool(items=[VG_A]).data["candidates"]}
    multi = {c["item_id"]: c["similarity"] for c in tool(items=[VG_A, EL_D]).data["candidates"]}
    assert multi[EL_A] > single[EL_A]  # both seeds contribute to EL_A


def test_item_cf_reports_unknown_seeds(corpus, cf_setup):
    interactions, _, item2id = cf_setup
    tool = ItemCFTool(ItemKNNRecommender(5).fit(interactions), item2id, corpus=corpus)
    only_unknown = tool(items=["Video_Games::zzz"])
    assert only_unknown.ok and only_unknown.data["candidates"] == []
    assert only_unknown.data["unknown_items"] == ["Video_Games::zzz"]
    mixed = tool(items=[VG_A, "Video_Games::zzz"])
    assert mixed.data["unknown_items"] == ["Video_Games::zzz"] and mixed.data["candidates"]


def test_item_cf_input_validation(corpus, cf_setup):
    interactions, _, item2id = cf_setup
    knn = ItemKNNRecommender(5).fit(interactions)
    assert not ItemCFTool(knn, item2id, corpus=corpus)(items=[]).ok
    assert not ItemCFTool(knn, item2id, corpus=corpus)(items=[VG_A], top_k=0).ok
    no_corpus = ItemCFTool(knn, item2id)
    assert no_corpus(items=[VG_A]).ok
    assert not no_corpus(items=[VG_A], domain="Electronics").ok  # domain filter needs a corpus
    with pytest.raises(TypeError):
        ItemCFTool(PopularityRecommender().fit(interactions), item2id)  # has no similarity matrix
