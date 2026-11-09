import numpy as np
import pytest
from scipy import sparse

from package.recommenders.evaluation.item_knn_matrix_recommender import ItemKNNMatrixRecommender
from package.recommenders.evaluation.hybrid_item_knn_recommender import HybridItemKNNRecommender
from package.evaluation.recommender.core.evaluate_recommender import evaluate_recommender


@pytest.mark.parametrize("weight", [0.25, 1, 4])
@pytest.mark.parametrize("k", [1, 10, 80])
def test_sparse_hybrid_matches_dense_formula(weight, k):
    rng = np.random.default_rng(29)
    train = sparse.csr_matrix((rng.random((12, 80)) < .1).astype(np.float32))
    cf = ItemKNNMatrixRecommender(k=5).fit(train)
    history = train.copy()
    history[0] = 0
    history.eliminate_zeros()
    model = HybridItemKNNRecommender(cf, history, weight)
    users = np.arange(12)
    scores = model.score_batch(users)
    a, b = history.nonzero()
    scores[a, b] = -np.inf
    expected = np.full((len(users), k), -1, dtype=np.int64)
    for row, values in enumerate(scores):
        ids = np.lexsort((np.arange(80), -values))[:k]
        ids = ids[values[ids] > -np.inf]
        expected[row, :len(ids)] = ids
    np.testing.assert_array_equal(model.recommend(users, k, history), expected)


def test_completion_uses_history_popularity_and_does_not_invent_cf_for_new_items():
    core = sparse.csr_matrix(([1, 1], ([0, 0], [0, 1])), shape=(3, 5), dtype=np.float32)
    cf = ItemKNNMatrixRecommender(k=1).fit(core)
    history = core.copy()
    history[1, 4] = history[2, 4] = 1
    model = HybridItemKNNRecommender(cf, history, 0)
    assert cf.similarity[4].nnz == 0
    assert model.recommend(np.array([0]), 2, history)[0].tolist() == [4, 2]
    excluded = sparse.csr_matrix(np.ones((3, 5)))
    assert model.recommend(np.array([0]), 2, excluded)[0].tolist() == [-1, -1]


def test_explicit_cohort_preserves_denominators_and_rejects_bad_users():
    core = sparse.eye(4, format="csr", dtype=np.float32)
    cf = ItemKNNMatrixRecommender(k=1).fit(core)
    model = HybridItemKNNRecommender(cf, core, 1)
    target = sparse.eye(4, format="csr")
    result = evaluate_recommender(model, core, target, [1], evaluation_users=np.array([0, 2]))
    assert result.num_users["all"] == 2
    assert result.overall["recall@1"] == 0
    for users in (np.array([0, 0]), np.array([5]), np.array([0.5])):
        with pytest.raises(ValueError):
            evaluate_recommender(model, core, target, [1], evaluation_users=users)


def test_familiarity_ratio_uses_only_selected_target_pairs():
    core = sparse.csr_matrix(([1], ([0], [0])), shape=(2, 3), dtype=np.float32)
    cf = ItemKNNMatrixRecommender(k=1).fit(core)
    model = HybridItemKNNRecommender(cf, core, 1)
    target = sparse.csr_matrix(([1, 1], ([0, 1], [0, 2])), shape=(2, 3))
    result = evaluate_recommender(model, core, target, [1], evaluation_users=np.array([1]))
    assert result.target_item_seen_ratio == 0
