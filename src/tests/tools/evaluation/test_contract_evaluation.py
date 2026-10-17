"""Contract tests for metrics, evaluate_recommender, EvaluationResult and segmentation.

All expected numbers are hand-derived from the tiny world (see tests/tools/conftest.py).  With the popularity
model, k=3 and the train matrix excluded, the recommendations and hit vectors are:

    user  recs (k=3)   target  hits        n_rel   segment (sparse_max=4)
    u0    [0, 1, 4]    {4}     [0, 0, 1]   1       cold   (0 interactions)
    u1    [1, 4, 5]    {3}     [0, 0, 0]   1       sparse (1)
    u2    [2, 3, -1]   {2, 3}  [1, 1, 0]   2       sparse (4 == sparse_max)
    u3    [3, -1, -1]  {3}     [1, 0, 0]   1       warm   (5)
    u4    [5, 2, 3]    {2}     [0, 1, 0]   1       sparse (3)
"""

import json
import math

import numpy as np
import pytest
import scipy.sparse as sp

from package.tools.evaluation import EvaluationResult, evaluate_recommender, ranking_metrics_at_k, segment_users_by_history_by_history
from package.tools.recommenders import PopularityMatrixRecommender, build_model

D2, D3 = 1 / math.log2(3), 0.5  # DCG discounts at ranks 2 and 3


@pytest.fixture
def result(world):
    model = PopularityMatrixRecommender().fit(world.train)
    return evaluate_recommender(model, world.train, world.target, [1, 3], sparse_max=4)


# ---------------------------------------------------------------- metric functions on tiny hit matrices
def test_metrics_hits_at_different_ranks():
    hits = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]], dtype=bool)
    m = ranking_metrics_at_k(hits, np.array([1, 1, 1, 1]), 3)
    assert m["precision@3"].tolist() == pytest.approx([1 / 3] * 3 + [0])
    assert m["recall@3"].tolist() == [1, 1, 1, 0]
    assert m["hit_rate@3"].tolist() == [1, 1, 1, 0]
    assert m["mrr@3"].tolist() == pytest.approx([1, 1 / 2, 1 / 3, 0])
    assert m["ndcg@3"].tolist() == pytest.approx([1, D2, D3, 0])
    assert m["map@3"].tolist() == pytest.approx([1, 1 / 2, 1 / 3, 0])


def test_metrics_multiple_relevant_items():
    # relevant = 3 items, hits at ranks 1 and 3 within k=3
    m = ranking_metrics_at_k(np.array([[1, 0, 1]], dtype=bool), np.array([3]), 3)
    assert m["precision@3"][0] == pytest.approx(2 / 3)
    assert m["recall@3"][0] == pytest.approx(2 / 3)
    assert m["ndcg@3"][0] == pytest.approx((1 + D3) / (1 + D2 + D3))
    assert m["map@3"][0] == pytest.approx((1 / 1 + 2 / 3) / 3)  # AP = (P@1 + P@3) / min(n_rel, k)
    assert m["mrr@3"][0] == 1


def test_metrics_k_smaller_than_hits_width_ignores_extra_columns():
    m = ranking_metrics_at_k(np.array([[0, 1, 1]], dtype=bool), np.array([2]), 1)
    assert m["precision@1"][0] == 0 and m["recall@1"][0] == 0


@pytest.mark.parametrize("hits, rel, k", [
    (np.zeros((2, 3), bool), np.array([1, 1]), 0),
    (np.zeros((2, 3), bool), np.array([1, 1]), 4),
    (np.zeros((2, 3), bool), np.array([1, 1]), True),
    (np.zeros((2, 3), bool), np.array([1, 0]), 2),
    (np.zeros((2, 3), bool), np.array([1, 1, 1]), 2),
    (np.zeros(3, bool), np.array([1]), 2),
    (np.array([[2, 0]]), np.array([1]), 1),
])
def test_metrics_reject_invalid_arguments(hits, rel, k):
    with pytest.raises(ValueError):
        ranking_metrics_at_k(hits, rel, k)


# ---------------------------------------------------------------- evaluate_recommender
def test_overall_metrics_at_3(result):
    o = result.overall
    assert o["precision@3"] == pytest.approx(1 / 3)
    assert o["recall@3"] == pytest.approx(0.8)
    assert o["hit_rate@3"] == pytest.approx(0.8)
    assert o["mrr@3"] == pytest.approx((1 / 3 + 0 + 1 + 1 + 1 / 2) / 5)
    assert o["ndcg@3"] == pytest.approx((D3 + 0 + 1 + 1 + D2) / 5)
    assert o["map@3"] == pytest.approx((1 / 3 + 0 + 1 + 1 + 1 / 2) / 5)


def test_overall_metrics_at_1(result):
    # k=1 recs: u0 [0] u1 [1] u2 [2] u3 [3] u4 [5] -> hits only for u2 (n_rel=2) and u3
    o = result.overall
    assert o["precision@1"] == pytest.approx(0.4)
    assert o["recall@1"] == pytest.approx((0 + 0 + 0.5 + 1 + 0) / 5)
    assert o["hit_rate@1"] == pytest.approx(0.4) and o["mrr@1"] == pytest.approx(0.4)
    assert o["ndcg@1"] == pytest.approx(0.4) and o["map@1"] == pytest.approx(0.4)


def test_padding_never_counts_as_a_hit_or_as_coverage(world):
    # u3's only recommendable item is 3; k=3 gives [3, -1, -1].  Column index -1 would be the LAST item (5):
    # make item 5 the target and check it is NOT credited.
    target = sp.csr_matrix(([1.0], ([3], [5])), shape=(6, 6))
    r = evaluate_recommender(PopularityMatrixRecommender().fit(world.train), world.train, target, [3])
    assert r.overall["hit_rate@3"] == 0.0 and r.overall["precision@3"] == 0.0
    assert r.catalog_coverage["catalog_coverage@3"] == pytest.approx(1 / 6)  # only item 3; -1 is not an item


def test_catalog_coverage(result):
    # k=1 distinct items {0,1,2,3,5}; k=3 distinct items: all six
    assert result.catalog_coverage == {"catalog_coverage@1": pytest.approx(5 / 6), "catalog_coverage@3": pytest.approx(1.0)}


def test_segments_and_counts(result):
    assert result.num_users == {"all": 5, "cold": 1, "sparse": 3, "warm": 1}
    seg = result.by_segment
    assert seg["cold"]["precision@3"] == pytest.approx(1 / 3) and seg["cold"]["mrr@3"] == pytest.approx(1 / 3)
    assert seg["warm"]["ndcg@3"] == pytest.approx(1.0) and seg["warm"]["recall@3"] == 1.0
    assert seg["sparse"]["precision@3"] == pytest.approx((0 + 2 / 3 + 1 / 3) / 3)
    assert seg["sparse"]["recall@3"] == pytest.approx(2 / 3)
    assert seg["sparse"]["mrr@3"] == pytest.approx((0 + 1 + 1 / 2) / 3)


@pytest.mark.parametrize("sparse_max, expected", [
    (4, {"cold": 1, "sparse": 3, "warm": 1}),   # 0 cold, 1/3/4 sparse, 5 warm
    (3, {"cold": 1, "sparse": 2, "warm": 2}),   # 4 interactions is now warm
    (0, {"cold": 1, "sparse": 0, "warm": 4}),
    (5, {"cold": 1, "sparse": 4, "warm": 0}),
])
def test_segment_boundaries(world, sparse_max, expected):
    r = evaluate_recommender(PopularityMatrixRecommender().fit(world.train), world.train, world.target, [3], sparse_max)
    assert {k: v for k, v in r.num_users.items() if k != "all"} == expected
    assert set(r.by_segment) == {s for s, n in expected.items() if n}  # empty segments are omitted from by_segment


def test_segments_come_from_fit_data_not_from_the_target(world):
    big_target = sp.csr_matrix(([1.0] * 5, ([0] * 5, [1, 2, 3, 4, 5])), shape=(6, 6))  # cold user with 5 targets
    r = evaluate_recommender(PopularityMatrixRecommender().fit(world.train), world.train, big_target, [3], 4)
    assert r.num_users == {"all": 1, "cold": 1, "sparse": 0, "warm": 0}


def test_target_item_seen_ratio(world):
    train = sp.csr_matrix(world.train[:, :5].toarray().astype(np.float32))  # model never saw item 5 ...
    train = sp.hstack([train, sp.csr_matrix((6, 1), dtype=np.float32)]).tocsr()
    target = sp.csr_matrix(([1.0, 1.0], ([0, 1], [4, 5])), shape=(6, 6))  # ... but one of two target pairs is item 5
    r = evaluate_recommender(PopularityMatrixRecommender().fit(train), train, target, [2])
    assert r.target_item_seen_ratio == pytest.approx(0.5)
    assert evaluate_recommender(PopularityMatrixRecommender().fit(world.train), world.train, world.target, [3]).target_item_seen_ratio == 1.0


def test_result_is_finite_and_json_serialisable(result):
    metrics = result.to_metrics(fit_seconds=1.2345)
    assert metrics["fit_seconds"] == 1.23 and set(metrics) >= {"overall", "by_segment", "num_users", "catalog_coverage", "target_item_seen_ratio"}
    json.dumps(metrics, allow_nan=False)  # raises on NaN/inf or numpy scalars
    assert isinstance(result, EvaluationResult)
    assert all(math.isfinite(v) for v in result.overall.values())


def test_metric_values_stay_in_unit_interval(world):
    for name in ("random", "popularity", "item_knn", "bpr_mf"):
        cfg = {"item_knn": {"k": 5}, "bpr_mf": {"embedding_dim": 4, "epochs": 2}}
        r = evaluate_recommender(build_model(name, cfg).fit(world.train), world.train, world.target, [1, 3])
        assert all(0.0 <= v <= 1.0 for v in r.overall.values()), (name, r.overall)


# ---------------------------------------------------------------- validation
def test_accepts_any_sparse_format_numpy_ints_and_ignores_stored_zeros_and_duplicates(world):
    model = PopularityMatrixRecommender().fit(world.train)
    base = evaluate_recommender(model, world.train, world.target, [3])
    assert evaluate_recommender(model, sp.coo_matrix(world.train), sp.coo_matrix(world.target), [np.int64(3)]).overall == base.overall
    # stored zero row for u5 + a duplicated entry must not create a phantom user nor double-count relevant items
    t = world.target.tocoo()
    noisy = sp.coo_matrix((np.append(t.data, [0.0, 1.0]), (np.append(t.row, [5, 0]), np.append(t.col, [0, 4]))), shape=t.shape)
    r = evaluate_recommender(model, world.train, noisy, [3])
    assert r.num_users["all"] == 5 and r.overall == base.overall


@pytest.mark.parametrize("ks, match", [
    ([], "non-empty"), (None, "non-empty"), ([0], "positive integers"), ([-1], "positive integers"),
    ([True], "positive integers"), ([2.5], "positive integers"), (["3"], "positive integers"),
    ([3, 3], "unique"), ([7], "cannot exceed num_items"),
])
def test_ks_validation(world, ks, match):
    with pytest.raises(ValueError, match=match):
        evaluate_recommender(PopularityMatrixRecommender().fit(world.train), world.train, world.target, ks)


@pytest.mark.parametrize("sparse_max", [-1, 1.5, True, "4", None])
def test_sparse_max_validation(world, sparse_max):
    with pytest.raises(ValueError, match="sparse_max"):
        evaluate_recommender(PopularityMatrixRecommender().fit(world.train), world.train, world.target, [3], sparse_max)


def test_matrix_validation(world):
    model = PopularityMatrixRecommender().fit(world.train)
    with pytest.raises(ValueError, match="same shape"):
        evaluate_recommender(model, sp.csr_matrix((5, 6)), world.target, [3])
    with pytest.raises(TypeError):
        evaluate_recommender(model, world.train, world.target.toarray(), [3])
    with pytest.raises(ValueError, match="fitted"):
        evaluate_recommender(PopularityMatrixRecommender(), world.train, world.target, [3])
    other = PopularityMatrixRecommender().fit(sp.csr_matrix(np.ones((6, 4), dtype=np.float32)))
    with pytest.raises(ValueError, match="item index spaces"):
        evaluate_recommender(other, world.train, world.target, [3])


def test_empty_evaluation_population_is_an_error_not_nan(world):
    with pytest.raises(ValueError, match="no interactions to evaluate"):
        evaluate_recommender(PopularityMatrixRecommender().fit(world.train), world.train, sp.csr_matrix((6, 6)), [3])
    only_zero = sp.csr_matrix(([0.0], ([0], [1])), shape=(6, 6))
    with pytest.raises(ValueError, match="no interactions to evaluate"):
        evaluate_recommender(PopularityMatrixRecommender().fit(world.train), world.train, only_zero, [3])


def test_k_equal_to_catalog_size_is_allowed(world):
    r = evaluate_recommender(PopularityMatrixRecommender().fit(world.train), world.train, world.target, [6])
    assert r.overall["recall@6"] == 1.0  # every unseen target item is somewhere in a full ranking


# ---------------------------------------------------------------- segment_users_by_history (tools.evaluation)
@pytest.mark.parametrize("sparse_max", [4])
def test_segment_users_by_history_boundaries(sparse_max):
    history = np.array([0, 1, 4, 5, 100])
    assert segment_users_by_history(range(5), history, sparse_max) == {0: "cold", 1: "sparse", 2: "sparse", 3: "warm", 4: "warm"}


def test_segment_users_by_history_edge_cases():
    history = np.array([0, 1, 2])
    assert segment_users_by_history([2, 0], history, 0) == {2: "warm", 0: "cold"}  # sparse_max=0: any history is warm
    assert segment_users_by_history([], history, 4) == {}
    assert segment_users_by_history(np.array([1, 1]), history, 4) == {1: "sparse"}


@pytest.mark.parametrize("users, history, sparse_max, exc", [
    ([3], np.array([0, 1, 2]), 4, ValueError), ([-1], np.array([0, 1, 2]), 4, ValueError),
    ([0], [0, 1], 4, TypeError), ([0], np.array([1]), -1, ValueError), ([0], np.array([1]), 1.5, ValueError),
])
def test_segment_users_by_history_validation(users, history, sparse_max, exc):
    with pytest.raises(exc):
        segment_users_by_history(users, history, sparse_max)


def test_segment_users_by_history_agrees_with_the_evaluator_when_given_the_fit_matrix(world):
    model = PopularityMatrixRecommender().fit(world.train)
    seg = segment_users_by_history(range(6), model.history_sizes(np.arange(6)), 4)
    assert seg == {0: "cold", 1: "sparse", 2: "sparse", 3: "warm", 4: "sparse", 5: "warm"}
