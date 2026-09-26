"""
Test các hàm EDA bằng dữ liệu SYNTHETIC (tự tạo, không phải Amazon Reviews
2023 thật). Mục đích: verify logic tính toán đúng, KHÔNG dùng để báo cáo
số liệu EDA thật (số liệu thật vẫn BLOCKED do network — xem
src/data/acquire.py và docs/limitations.md).
"""

import pandas as pd
import pytest

from package.data.eda import compute_interaction_stats, k_core_filter, segment_users


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
        synthetic_interactions, min_user_interactions=3, min_item_interactions=2
    )
    # chỉ u1 có >=3 interaction; sau khi lọc theo item >=2, item i3 (chỉ
    # xuất hiện 1 lần với u1) cũng bị loại vì count toàn cục của i3 là 2
    # (u1 + u2) nhưng u2 đã bị loại ở vòng lặp trước -> cần kiểm tra hội tụ
    remaining_users = set(filtered["user_id"])
    assert "u3" not in remaining_users  # u3 chỉ có 1 interaction, chắc chắn bị loại
    assert len(filtered) <= len(synthetic_interactions)


def test_segment_users_assigns_new_sparse_warm(synthetic_interactions):
    segments = segment_users(
        synthetic_interactions, as_of_timestamp=600, sparse_threshold=2
    )
    seg_map = dict(zip(segments["user_id"], segments["segment"]))
    assert seg_map["u1"] == "warm"       # 5 interaction > threshold
    assert seg_map["u2"] == "sparse_history"  # 2 interaction == threshold
    assert seg_map["u3"] == "sparse_history"  # 1 interaction <= threshold

    # evolving_interest phải là False khi không có category data — không
    # được tự suy diễn khi thiếu dữ liệu (mục XXVIII)
    assert not segments["evolving_interest"].any()


def test_segment_users_respects_as_of_timestamp(synthetic_interactions):
    # tại t=200, u1 chỉ mới có 2 interaction (timestamp 100, 200)
    segments = segment_users(
        synthetic_interactions, as_of_timestamp=200, sparse_threshold=2
    )
    seg_map = dict(zip(segments["user_id"], segments["segment"]))
    assert seg_map["u1"] == "sparse_history"  # đúng 2 <= threshold tại thời điểm này
    assert "u3" not in seg_map  # u3 chưa có interaction nào trước t=200
