"""Hai họ ItemKNN (DataFrame cho tool/agent, ma trận cho đánh giá offline) phải cho cùng ma trận similarity.

Chúng KHÁC nhau ở hướng chấm điểm khi k nhỏ (history @ S  vs  history @ S.T) — xem docstring từng lớp.
Khi k >= số item - 1 (không cắt láng giềng) S đối xứng nên hai hướng trùng nhau; test này khoá cả hai điều đó.
"""

import numpy as np
import pandas as pd
import scipy.sparse as sp

from package.tools.recommenders.baseline_item_knn import ItemKNNRecommender as DataFrameKNN
from package.tools.recommenders.item_knn import ItemKNNRecommender as MatrixKNN


def _interactions(seed: int = 0, users: int = 30, items: int = 12) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dense = rng.random((users, items)) < 0.3
    u, i = np.nonzero(dense)
    return pd.DataFrame({"user_idx": u, "item_idx": i})


def test_similarity_matches_without_neighbor_cut():
    frame = _interactions()
    items = int(frame["item_idx"].max()) + 1
    users = int(frame["user_idx"].max()) + 1
    matrix = sp.csr_matrix((np.ones(len(frame), dtype=np.float32), (frame["user_idx"], frame["item_idx"])), shape=(users, items))

    a = DataFrameKNN(neighbors=items).fit(frame).similarity.toarray()
    b = MatrixKNN(k=items, block_elements=1000).fit(matrix).similarity.toarray()
    np.testing.assert_allclose(a[: b.shape[0], : b.shape[1]], b, atol=1e-5)


def test_top_recommendations_agree_without_neighbor_cut():
    frame = _interactions(seed=1)
    items = int(frame["item_idx"].max()) + 1
    users = int(frame["user_idx"].max()) + 1
    matrix = sp.csr_matrix((np.ones(len(frame), dtype=np.float32), (frame["user_idx"], frame["item_idx"])), shape=(users, items))

    df_knn = DataFrameKNN(neighbors=items).fit(frame)
    mat_knn = MatrixKNN(k=items, block_elements=1000).fit(matrix)
    scores = mat_knn.score_batch(np.arange(users))
    for user in range(users):
        seen = set(frame.loc[frame["user_idx"] == user, "item_idx"])
        ranked = [i for i in np.argsort(-scores[user], kind="stable") if i not in seen and scores[user][i] > 0][:3]
        got = [i for i in df_knn.recommend(user, 3) if scores[user][i] > 0]
        assert set(got[: len(ranked)]) == set(ranked[: len(got)]) or not ranked
