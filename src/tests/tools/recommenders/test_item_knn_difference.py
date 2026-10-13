"""
Test minh họa sự khác biệt giữa hai họ ItemKNN khi k nhỏ.

Test này chỉ để minh họa sự khác biệt trong tài liệu, không phải contract test.
Hai họ khác nhau khi k nhỏ vì:
- DataFrame (baseline_item_knn): score dựa trên top-k láng giềng của các item trong history
- Matrix (item_knn): score dựa trên top-k láng giềng của chính item được chấm (do S.T)
"""

import numpy as np
import pandas as pd
import scipy.sparse as sp
import pytest

from package.tools.recommenders.baseline_item_knn import ItemKNNRecommender as DataFrameKNN
from package.tools.recommenders.item_knn import ItemKNNRecommender as MatrixKNN


def test_item_knn_top_k_difference():
    """
    Minh họa: hai họ ItemKNN cho top-k khác nhau khi k nhỏ.
    
    Thiết lập:
    - 3 users, 5 items
    - k=2 (cắt láng giềng, không phải full similarity)
    - User 0 có history [0, 1]
    
    Kết quả:
    - DataFrame: score(item_j) = Σ similarity(item_i, item_j) với i ∈ history
      → dựa trên top-2 láng giềng của item 0 và item 1
    - Matrix: score(item_j) = Σ similarity(item_j, item_i) với i ∈ history
      → dựa trên top-2 láng giềng của chính item j
    
    Khi k nhỏ, hai hướng khác nhau vì similarity matrix không đối xứng.
    """
    # Tạo interaction matrix
    # User 0: items 0, 1
    # User 1: items 1, 2
    # User 2: items 2, 3
    interactions = pd.DataFrame({
        "user_idx": [0, 0, 1, 1, 2, 2],
        "item_idx": [0, 1, 1, 2, 2, 3],
    })
    
    users = 3
    items = 5
    matrix = sp.csr_matrix(
        (np.ones(len(interactions), dtype=np.float32), 
         (interactions["user_idx"], interactions["item_idx"])),
        shape=(users, items)
    )
    
    k = 2  # Cắt láng giềng nhỏ để thấy sự khác biệt
    
    # Fit cả hai họ
    df_knn = DataFrameKNN(neighbors=k).fit(interactions)
    mat_knn = MatrixKNN(k=k, block_elements=1000).fit(matrix)
    
    # Lấy top-3 recommendation cho user 0
    df_recs = df_knn.recommend(0, 3)
    mat_scores = mat_knn.score_batch(np.array([0]))[0]
    
    # Lấy top-3 từ matrix (loại bỏ seen items)
    seen = set(interactions.loc[interactions["user_idx"] == 0, "item_idx"])
    mat_recs = [i for i in np.argsort(-mat_scores) if i not in seen and mat_scores[i] > 0][:3]
    
    # Hai họ có thể cho kết quả khác nhau
    # (không assert cụ thể vì phụ thuộc vào dữ liệu synthetic)
    print(f"DataFrame KNN (k={k}): {df_recs}")
    print(f"Matrix KNN (k={k}): {mat_recs}")
    
    # Chỉ kiểm tra cả hai trả về something (không rỗng)
    assert len(df_recs) > 0, "DataFrame KNN should return recommendations"
    assert len(mat_recs) > 0, "Matrix KNN should return recommendations"
    
    # Kiểm tra khi k lớn (không cắt) thì hai họ trùng nhau
    df_knn_full = DataFrameKNN(neighbors=items).fit(interactions)
    mat_knn_full = MatrixKNN(k=items, block_elements=1000).fit(matrix)
    
    df_recs_full = df_knn_full.recommend(0, 3)
    mat_scores_full = mat_knn_full.score_batch(np.array([0]))[0]
    mat_recs_full = [i for i in np.argsort(-mat_scores_full) if i not in seen and mat_scores_full[i] > 0][:3]
    
    print(f"DataFrame KNN (k={items}, no cut): {df_recs_full}")
    print(f"Matrix KNN (k={items}, no cut): {mat_recs_full}")
    
    # Khi không cắt, hai họ nên trùng nhau (hoặc ít nhất top-1 trùng)
    assert set(df_recs_full[:1]) == set(mat_recs_full[:1]), (
        "When k >= num_items-1 (no cut), both families should agree on top-1"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
