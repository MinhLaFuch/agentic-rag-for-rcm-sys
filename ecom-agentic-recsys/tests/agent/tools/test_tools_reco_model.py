from src.recommenders.baselines import ItemKNNRecommender, PopularityRecommender
from src.tools import BaselineScorer, ItemCFTool, RecoModelTool, SQLTool
from tests.tools_helpers import EL_A, EL_D, VG_A, VG_B, VG_C


def _reco(corpus, cf_setup, model_cls=ItemKNNRecommender):
    interactions, user2id, item2id = cf_setup
    model = model_cls(5).fit(interactions) if model_cls is ItemKNNRecommender else model_cls().fit(interactions)
    return RecoModelTool(BaselineScorer(model), user2id, item2id, corpus=corpus)


def test_reco_ranks_candidates_and_drops_seen_items(corpus, cf_setup):
    tool = _reco(corpus, cf_setup)
    # u2 has seen VG_A and VG_B; u2's neighbours favour EL_A over EL_D
    result = tool(user_id="u2", candidates=[VG_A, VG_B, EL_D, EL_A])
    assert result.ok
    assert [r["item_id"] for r in result.data["ranked"]] == [EL_A, EL_D]
    assert [r["rank"] for r in result.data["ranked"]] == [1, 2]
    assert sorted(result.data["excluded_seen"]) == [VG_A, VG_B]
    assert result.data["ranked"][0]["score"] > result.data["ranked"][1]["score"]
    assert result.data["cold_start"] is False


def test_reco_can_keep_seen_items(corpus, cf_setup):
    tool = _reco(corpus, cf_setup)
    result = tool(user_id="u2", candidates=[VG_A, EL_A], exclude_seen=False)
    assert {r["item_id"] for r in result.data["ranked"]} == {VG_A, EL_A}
    assert result.data["excluded_seen"] == []


def test_reco_accepts_other_tools_output_directly(corpus, cf_setup):
    interactions, user2id, item2id = cf_setup
    knn = ItemKNNRecommender(5).fit(interactions)
    cf = ItemCFTool(knn, item2id, corpus=corpus)
    reco = RecoModelTool(BaselineScorer(knn), user2id, item2id, corpus=corpus)
    candidates = cf(items=[VG_A]).data["candidates"]
    assert reco(user_id="u3", candidates=candidates).ok
    sql_candidates = SQLTool(corpus)().data["candidates"]
    assert reco(user_id="u3", candidates=sql_candidates).ok


def test_reco_reports_items_the_model_has_never_seen(corpus, cf_setup):
    result = _reco(corpus, cf_setup)(user_id="u3", candidates=[VG_B, VG_C])
    assert result.data["unscored_item_ids"] == [VG_C]  # in corpus, but not in the CF/mapping vocabulary
    assert [r["item_id"] for r in result.data["ranked"]] == [VG_B]


def test_reco_cold_start_user_falls_back_to_popularity(corpus, cf_setup):
    tool = _reco(corpus, cf_setup)
    result = tool(user_id="brand_new_user", candidates=[EL_D, VG_A, EL_A])
    assert result.ok and result.data["cold_start"] is True
    top_ids = [r["item_id"] for r in result.data["ranked"]]
    assert EL_D == top_ids[-1]  # least popular item ranks last
    assert set(top_ids) == {EL_D, VG_A, EL_A}  # nothing dropped: no history to exclude


def test_reco_top_k_domain_and_input_validation(corpus, cf_setup):
    tool = _reco(corpus, cf_setup)
    result = tool(user_id="u1", candidates=[VG_B, EL_D], top_k=1)
    assert len(result.data["ranked"]) == 1 and "domain" in result.data["ranked"][0]
    assert not tool(user_id="u1", candidates=[]).ok
    assert not tool(user_id="u1", candidates=[VG_B], top_k=0).ok
    assert not tool(user_id="u1", candidates=[{"no_item_id": 1}]).ok


def test_reco_works_with_a_popularity_model_and_without_a_corpus(cf_setup):
    interactions, user2id, item2id = cf_setup
    tool = RecoModelTool(BaselineScorer(PopularityRecommender().fit(interactions)), user2id, item2id)
    result = tool(user_id="u1", candidates=[VG_B, EL_D])
    assert result.ok and result.data["model"] == "PopularityRecommender"
    assert "domain" not in result.data["ranked"][0]


def test_reco_ties_keep_input_order(cf_setup):
    interactions, user2id, item2id = cf_setup
    tool = RecoModelTool(BaselineScorer(PopularityRecommender().fit(interactions)), user2id, item2id)
    forward = tool(user_id="brand_new_user", candidates=[VG_B, EL_D]).data["ranked"]
    backward = tool(user_id="brand_new_user", candidates=[EL_D, VG_B]).data["ranked"]
    assert forward[0]["score"] == forward[1]["score"]  # VG_B and EL_D are equally popular
    assert [r["item_id"] for r in forward] == [VG_B, EL_D]
    assert [r["item_id"] for r in backward] == [EL_D, VG_B]
