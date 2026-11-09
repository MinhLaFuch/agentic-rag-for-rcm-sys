from types import SimpleNamespace

import numpy as np
import pytest
from scipy import sparse

from package.tools.score.hybrid_scorer import HybridScorer
from package.tools.recommenders.item_knn_matrix_recommender import ItemKNNMatrixRecommender
from package.tools.recommenders.hybrid_item_knn_recommender import HybridItemKNNRecommender


@pytest.mark.parametrize("weight", [0.5, 4])
def test_candidate_scores_match_full_catalog_hybrid_with_global_normalization(weight):
    history = sparse.csr_matrix([[1, 1, 0, 0], [0, 0, 0, 1]], dtype=np.float32)
    similarity = sparse.csr_matrix([[0, 0, .2, .8], [0, 0, .1, 0], [0, 0, 0, 0], [0, 0, 0, 0]], dtype=np.float32)
    knn = SimpleNamespace(user_items=history, similarity=similarity, num_items=4, scores=np.array([8, 2, 0, 0]))
    scorer = HybridScorer(knn, weight)
    cf = ItemKNNMatrixRecommender(k=2)
    cf.train_matrix = history
    cf.similarity = similarity.T.tocsr()
    cf.num_users, cf.num_items = history.shape
    model = HybridItemKNNRecommender(cf, history, weight)
    for user in (0, 1):
        expected = model.score_batch(np.array([user]))[0]
        np.testing.assert_allclose(scorer.score(user, np.array([2, 0, 3])), expected[[2, 0, 3]])
        # Candidate subsets cannot change normalization.
        np.testing.assert_allclose(scorer.score(user, np.array([2])), expected[[2]])
    assert scorer.seen_items(0) == {0, 1}
    assert scorer.score(999, np.array([-1, 0, 99])).tolist() == [0, weight, 0]
    assert knn.scores.tolist() == [8, 2, 0, 0]


def test_hybrid_weight_validation():
    knn = SimpleNamespace(user_items=sparse.eye(2, format="csr"), similarity=sparse.eye(2, format="csr"), num_items=2)
    for weight in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            HybridScorer(knn, weight)
