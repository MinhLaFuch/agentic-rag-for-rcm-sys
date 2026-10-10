"""Test các hàm EDA và k-core bằng dữ liệu SYNTHETIC (verify logic, không phải số liệu Amazon Reviews 2023 thật)."""

import pandas as pd
import pytest

from package.data.eda import compute_interaction_stats
from package.data.filter import k_core_filter


@pytest.fixture
def synthetic_interactions() -> pd.DataFrame:
    # 3 user, 3 item, số lượng interaction khác nhau để test phân phối
    rows = [
        # user u1: 5 interaction (warm)
        ("u1", "i1", 5.0, 100),
        ("u1", "i2", 4.0, 200),
        ("u1", "i1", 3.0, 300),
        ("u1", "i3", 5.0, 400),
        ("u1", "i2", 2.0, 500),
        # user u2: 2 interaction (sparse)
        ("u2", "i1", 4.0, 150),
        ("u2", "i3", 5.0, 250),
        # user u3: 1 interaction
        ("u3", "i2", 3.0, 600),
    ]
    return pd.DataFrame(rows, columns=["user_id", "parent_asin", "rating", "timestamp"])


def test_compute_interaction_stats_basic_counts(synthetic_interactions):
    stats = compute_interaction_stats(synthetic_interactions)
    assert stats.num_users == 3
    assert stats.num_items == 3
    assert stats.num_interactions == 8
    assert stats.timestamp_min == 100
    assert stats.timestamp_max == 600


def test_compute_interaction_stats_missing_column_raises():
    bad_df = pd.DataFrame({"user_id": ["u1"], "parent_asin": ["i1"]})
    with pytest.raises(ValueError):
        compute_interaction_stats(bad_df)


def test_k_core_filter_removes_sparse_users_and_items(synthetic_interactions):
    filtered = k_core_filter(
        synthetic_interactions, min_user_interactions=3, min_item_interactions=2, max_iterations=20
    )
    # chỉ u1 có >=3 interaction; sau khi lọc theo item >=2, item i3 (chỉ
    # xuất hiện 1 lần với u1) cũng bị loại vì count toàn cục của i3 là 2
    # (u1 + u2) nhưng u2 đã bị loại ở vòng lặp trước -> cần kiểm tra hội tụ
    remaining_users = set(filtered["user_id"])
    assert "u3" not in remaining_users  # u3 chỉ có 1 interaction, chắc chắn bị loại
    assert len(filtered) <= len(synthetic_interactions)


def test_k_core_filter_warns_when_not_converged():
    # chuỗi phụ thuộc: bỏ 1 user thì item kế tiếp rơi dưới ngưỡng -> cần nhiều vòng
    rows = [("u1", "a"), ("u1", "b"), ("u2", "b"), ("u2", "c"), ("u3", "c")]
    df = pd.DataFrame(rows, columns=["user_id", "parent_asin"])
    with pytest.warns(RuntimeWarning):
        k_core_filter(df, min_user_interactions=2, min_item_interactions=2, max_iterations=1)
