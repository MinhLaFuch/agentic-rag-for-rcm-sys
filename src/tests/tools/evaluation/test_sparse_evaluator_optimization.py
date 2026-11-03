import numpy as np
import pytest
from scipy import sparse

from package.tools.recommenders import build_model, Recommender
from package.tools.evaluation.evaluate_recommender import evaluate_recommender


def reference(model, users, k, exclude):
    scores = np.array(model.score_batch(users), dtype=np.float32, copy=True)
    rows, cols = exclude[users].nonzero()
    scores[rows, cols] = -np.inf
    popularity = np.asarray(model.train_matrix.sum(axis=0)).ravel().astype(np.float32)
    out = np.full((len(users), k), -1, dtype=np.int64)
    for row, values in enumerate(scores):
        valid = values > -np.inf
        if valid.any() and (values[valid] == 0).all():
            values[valid] = popularity[valid]
        ids = np.lexsort((np.arange(len(values)), -values))[:k]
        ids = ids[values[ids] > -np.inf]
        out[row, :len(ids)] = ids
    return out


@pytest.mark.parametrize("k", [1, 7, 70])
def test_dense_partition_preserves_boundary_ties_and_negative_scores(k):
    class Dense(Recommender):
        def _fit(self, train_matrix):
            pass

        def score_batch(self, users):
            return values[users]

    rng = np.random.default_rng(18)
    values = rng.integers(-3, 4, (12, 70)).astype(np.float32)
    values[0] = 0
    values[1, 4] = np.inf
    train = sparse.csr_matrix((rng.random((12, 70)) < .1).astype(np.float32))
    model = Dense().fit(train)
    users = np.arange(12)
    np.testing.assert_array_equal(model.recommend(users, k, train), reference(model, users, k, train))


@pytest.mark.parametrize("name", ["popularity", "item_knn"])
@pytest.mark.parametrize("k", [1, 7, 70])
def test_sparse_topk_equals_full_sort_and_never_scores_dense(name, k, monkeypatch):
    rng = np.random.default_rng(32)
    train = sparse.csr_matrix((rng.random((20, 70)) < .12).astype(np.float32))
    train[0] = 0
    train.eliminate_zeros()
    model = build_model(name, {"item_knn": {"k": 8}}).fit(train)
    exclude = train.copy()
    exclude[1] = 1
    exclude.eliminate_zeros()
    users = np.arange(20)
    expected = reference(model, users, k, exclude)
    monkeypatch.setattr(model, "score_batch", lambda *a: pytest.fail("dense scores requested"))
    np.testing.assert_array_equal(model.recommend(users, k, exclude), expected)


def test_sparse_ground_truth_and_progress_match_reference(capsys, monkeypatch):
    rng = np.random.default_rng(19)
    train = sparse.csr_matrix((rng.random((40, 100)) < .08).astype(np.float32))
    target = sparse.csr_matrix((rng.random((40, 100)) < .03).astype(np.float32))
    model = build_model("item_knn", {"item_knn": {"k": 5}}).fit(train)
    original = model.recommend
    monkeypatch.setattr(model, "recommend", lambda users, k, exclude: reference(model, users, k, exclude))
    expected = evaluate_recommender(model, train, target, [1, 5, 10]).to_metrics(0)
    monkeypatch.setattr(model, "recommend", original)
    # CSR ground truth must not be converted into batch x catalog arrays.
    monkeypatch.setattr(sparse.csr_matrix, "toarray", lambda *a, **k: pytest.fail("dense ground truth requested"))
    actual = evaluate_recommender(model, train, target, [1, 5, 10], progress_every=10).to_metrics(0)
    assert actual == expected
    output = capsys.readouterr().out
    assert "ETA=" in output and "100.00%" in output and "this model" in output
