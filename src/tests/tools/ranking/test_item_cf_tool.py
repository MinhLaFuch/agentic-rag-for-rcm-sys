import pytest

from package.tools.recommenders import ItemKNNRecommender, PopularityRecommender
from package.tools import ItemCFTool
from tests.tools_helpers import EL_A, EL_D, VG_A


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
