"""Integration tests: do the modules agree with each other at their boundaries? (tiny world, hand-checked values)

1. DataFrame -> ItemCorpus -> SQLTool -> item ids
2. query -> SemanticSearchTool -> candidates -> RecoModelTool ranking
3. train matrix -> recommender.fit -> score_batch -> recommend
4. cold user -> popularity fallback -> final recommendations
5. fitted recommender -> evaluator -> metrics / EvaluationResult
6. config merge -> model factory -> fit -> recommend
"""

import math

import numpy as np
import pandas as pd
import pytest

from package.tools import (
    BaselineScorer, ItemCFTool, ItemCorpus, QueryTool, RecoModelTool, SemanticSearchTool, SQLTool,
)
from package.tools.evaluation import evaluate_recommender, merge_model_params
from package.tools.recommenders import (
    FallbackRecommender, ItemKNNMatrixRecommender, ItemKNNRecommender, PopularityMatrixRecommender,
    PopularityRecommender, build_model,
)
from tests.tools.conftest import ITEMS, POPULARITY_ORDER


def _ids(result, key="candidates"):
    assert result.ok, result.error
    return [c["item_id"] for c in result.data[key]]


# ------------------------------------------------------------------------- 1. DataFrame -> corpus -> SQLTool -> ids
def test_dataframe_to_corpus_to_sql_tool_to_item_ids(world):
    sql = SQLTool(world.corpus)
    games_cheap = sql(filters={"domain": "Games", "price_max": 50, "include_missing_price": True})
    assert _ids(games_cheap) == ["Games::A1", "Games::B2", "Games::C3"]  # by rating_number: 120, 80, 40
    # every id the SQL tool returns maps to an index of the model vocabulary and back to the same domain
    assert all(i in world.item2id for i in _ids(games_cheap))
    assert set(world.corpus.item_domains(_ids(games_cheap)).values()) == {"Games"}
    # the same original id in two domains stays two items end to end
    both = QueryTool(world.corpus)(item_ids=["Toys::A1", "Games::A1"])
    assert [(i["item_id"], i["domain"], i["original_item_id"]) for i in both.data["items"]] == [
        ("Toys::A1", "Toys", "A1"), ("Games::A1", "Games", "A1")]
    assert _ids(sql(filters={"exclude_item_ids": ["Toys::A1"], "categories_any": ["Toys"]})) == ["Toys::E5"]


def test_missing_metadata_survives_the_whole_path(world):
    d4 = QueryTool(world.corpus)(item_ids=["Games::D4"]).data["items"][0]
    assert d4["store"] is None and d4["average_rating"] is None and d4["rating_number"] is None
    assert "Games::D4" in _ids(SQLTool(world.corpus)(filters={"domain": "Games"}))
    assert "Games::D4" not in _ids(SQLTool(world.corpus)(filters={"min_rating": 0}))  # NULL rating never matches


# ------------------------------------------------------------------------- 2. search -> candidates -> scoring/ranking
def test_search_candidates_feed_the_ranker_directly(world):
    search = SemanticSearchTool(world.corpus)
    found = search(query="wireless headset")  # B2 matches 'wireless', C3 matches 'headset' (no stem collisions)
    assert set(_ids(found)) == {"Games::B2", "Games::C3"}
    reco = RecoModelTool(BaselineScorer(PopularityRecommender().fit(world.interactions)), world.user2id, world.item2id,
                         corpus=world.corpus)
    # the candidate dicts are passed as-is (output of one tool = input of the next)
    cold = reco(user_id="stranger", candidates=found.data["candidates"])
    assert [r["item_id"] for r in cold.data["ranked"]] == ["Games::B2", "Games::C3"]  # popularity 4 > 2
    u2 = reco(user_id="u2", candidates=found.data["candidates"])  # u2 already has B2
    assert [r["item_id"] for r in u2.data["ranked"]] == ["Games::C3"] and u2.data["excluded_seen"] == ["Games::B2"]


def test_search_with_filters_then_item_cf_then_ranker(world):
    knn = ItemKNNRecommender(neighbors=5).fit(world.interactions)
    cf = ItemCFTool(knn, world.item2id, corpus=world.corpus)
    reco = RecoModelTool(BaselineScorer(knn), world.user2id, world.item2id, corpus=world.corpus)
    similar = cf(items=["Games::A1"], domain="Toys")
    ranked = reco(user_id="u1", candidates=similar.data["candidates"])
    # u1 saw only Games::A1 -> both Toys items are unseen; order follows similarity to A1 (tie -> input order)
    assert [r["item_id"] for r in ranked.data["ranked"]] == ["Toys::A1", "Toys::E5"]
    assert {r["domain"] for r in ranked.data["ranked"]} == {"Toys"}


# ------------------------------------------------------------------------- 3. train matrix -> fit -> score -> recommend
def test_train_matrix_fit_score_batch_recommend(world):
    pop = PopularityMatrixRecommender().fit(world.train)
    assert pop.score_batch(np.array([0, 3]))[1].tolist() == [5, 4, 2, 1, 4, 3]
    assert pop.recommend(np.array([0]), 6)[0].tolist() == POPULARITY_ORDER

    knn = ItemKNNMatrixRecommender(k=5).fit(world.train)
    assert knn.similarity[0, 1] == pytest.approx(4 / math.sqrt(20), abs=1e-6)
    recs = knn.recommend(np.arange(6), 6, world.train)
    assert recs[3].tolist() == [3, -1, -1, -1, -1, -1]  # u3: one recommendable item; the rest is padding
    assert recs[5].tolist() == [-1] * 6  # u5 saw everything
    assert recs[1].tolist() == [1, 4, 5, 2, 3, -1]  # u1: ordered by similarity to item 0 (ties -> smaller idx)


def test_vocabulary_is_shared_between_corpus_and_models(world):
    """item2id order == corpus order == matrix columns: ids returned by tools can index the model matrices."""
    assert list(world.item2id) == ITEMS
    assert world.corpus.item_domains(ITEMS).keys() == set(ITEMS)
    assert world.train.shape == (len(world.user2id), len(world.item2id))


# ------------------------------------------------------------------------- 4. cold user -> popularity fallback
@pytest.mark.parametrize("how", ["manual", "factory"])
def test_cold_user_gets_popularity_through_the_fallback(world, how):
    if how == "manual":
        model = FallbackRecommender(ItemKNNMatrixRecommender(k=5), PopularityMatrixRecommender())
    else:
        model = build_model("item_knn", {"item_knn": {"k": 5}, "popularity_fallback": True})
    model.fit(world.train)
    assert model.recommend(np.array([0]), 6)[0].tolist() == POPULARITY_ORDER
    # warm users are NOT overridden: ItemKNN scores still apply (u2's remaining items are 2 and 3)
    assert model.recommend(np.array([2]), 3, world.train)[0].tolist() == [2, 3, -1]


def test_without_fallback_a_cold_user_still_gets_popularity_via_the_zero_signal_rule(world):
    plain = build_model("item_knn", {"item_knn": {"k": 5}, "popularity_fallback": False}).fit(world.train)
    assert plain.recommend(np.array([0]), 6)[0].tolist() == POPULARITY_ORDER


# ------------------------------------------------------------------------- 5. recommender -> evaluator -> result
def test_fitted_recommender_to_evaluator_to_result(world):
    model = build_model("popularity", {}).fit(world.train)
    result = evaluate_recommender(model, world.train, world.target, [1, 3])
    assert result.num_users == {"all": 5, "cold": 1, "sparse": 3, "warm": 1}
    assert result.overall["recall@3"] == pytest.approx(0.8) and result.overall["precision@1"] == pytest.approx(0.4)
    assert result.catalog_coverage["catalog_coverage@3"] == pytest.approx(1.0)
    metrics = result.to_metrics(fit_seconds=0.5)
    assert metrics["num_users"]["all"] == 5 and metrics["fit_seconds"] == 0.5


def test_evaluator_and_standalone_metrics_agree_with_the_legacy_evaluation(world):
    """Same model idea through the OTHER API family: legacy evaluate_ranking on user 0 (cold): recs [0,1,4], target {4}."""
    from package.tools.evaluation import evaluate_ranking

    legacy = PopularityRecommender().fit(world.interactions)
    out = evaluate_ranking(legacy, pd.DataFrame({"user_idx": [0], "item_idx": [4]}), [3])
    assert out["precision@3"] == pytest.approx(1 / 3) and out["recall@3"] == 1 and out["mrr@3"] == pytest.approx(1 / 3)
    assert out["ndcg@3"] == pytest.approx(0.5) and out["map@3"] == pytest.approx(1 / 3) and out["evaluated_users"] == 1
    new = evaluate_recommender(PopularityMatrixRecommender().fit(world.train), world.train,
                               _only_user(world.target, 0), [3])
    assert new.overall["mrr@3"] == pytest.approx(out["mrr@3"]) and new.overall["ndcg@3"] == pytest.approx(out["ndcg@3"])


def _only_user(matrix, user):
    import scipy.sparse as sp

    keep = sp.lil_matrix(matrix.shape, dtype=matrix.dtype)
    keep[user, :] = matrix[user, :]
    return keep.tocsr()


# ------------------------------------------------------------------------- 6. config merge -> factory -> fit -> recommend
def test_config_merge_to_factory_to_fit_to_recommend(world):
    base = {"seed": 42, "popularity_fallback": True, "bpr_mf": {"embedding_dim": 64, "epochs": 20, "batch_size": 2048}}
    merged = merge_model_params(base, "bpr_mf", {"embedding_dim": 4, "epochs": 3, "batch_size": 4})
    assert base["bpr_mf"]["epochs"] == 20  # the base config is untouched
    model = build_model("bpr_mf", merged)
    assert isinstance(model, FallbackRecommender) and model.primary.embedding_dim == 4 and model.primary.seed == 42
    model.fit(world.train)
    recs = model.recommend(np.arange(6), 3, world.train)
    assert recs.shape == (6, 3) and recs[0].tolist() == [0, 1, 4]  # u0 is cold -> popularity fallback
    assert recs[5].tolist() == [-1, -1, -1]
    again = build_model("bpr_mf", merged).fit(world.train).recommend(np.arange(6), 3, world.train)
    assert (again == recs).all()  # same config + seed -> same recommendations


def test_merged_config_for_a_model_that_cannot_use_a_parameter_fails_loudly():
    merged = merge_model_params({"seed": 1}, "item_knn", {"neighbours": 5})  # typo: not a real parameter
    with pytest.raises(TypeError):
        build_model("item_knn", merged)
