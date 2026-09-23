import gzip
import json

import pytest

from data.train.mapping import compute_interaction_stats_streaming


@pytest.fixture
def synthetic_review_file(tmp_path):
    rows = [
        {"user_id": "u1", "parent_asin": "i1", "rating": 5.0, "timestamp": 100},
        {"user_id": "u1", "parent_asin": "i2", "rating": 4.0, "timestamp": 200},
        {"user_id": "u1", "parent_asin": "i1", "rating": 3.0, "timestamp": 300},
        {"user_id": "u2", "parent_asin": "i1", "rating": 4.0, "timestamp": 150},
        {"user_id": "u3", "parent_asin": "i2", "rating": 3.0, "timestamp": 600},
    ]
    path = tmp_path / "review_test.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def test_streaming_stats_basic(synthetic_review_file):
    stats = compute_interaction_stats_streaming(str(synthetic_review_file))
    assert stats.num_interactions == 5
    assert stats.num_users == 3
    assert stats.num_items == 2
    assert stats.timestamp_min == 100
    assert stats.timestamp_max == 600
    assert stats.interactions_per_user["u1"] == 3
    assert stats.interactions_per_user["u2"] == 1
    assert stats.interactions_per_user["u3"] == 1


def test_streaming_stats_avg_rating(synthetic_review_file):
    stats = compute_interaction_stats_streaming(str(synthetic_review_file))
    expected_avg = (5.0 + 4.0 + 3.0 + 4.0 + 3.0) / 5
    assert stats.rating_sum / stats.num_interactions == pytest.approx(expected_avg)


def test_streaming_stats_supports_uncompressed_jsonl(tmp_path):
    path = tmp_path / "review_test.jsonl"
    path.write_text(
        '{"user_id": "u1", "parent_asin": "i1", "rating": 5, "timestamp": 100}\n',
        encoding="utf-8",
    )

    stats = compute_interaction_stats_streaming(path)

    assert stats.num_interactions == 1
    assert stats.num_users == 1
    assert stats.num_items == 1
