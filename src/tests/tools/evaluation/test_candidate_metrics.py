import numpy as np
import pytest

from package.tools.evaluation import candidate_retrieval_metrics, item_familiarity_metrics, latency_summary
from scripts.evaluation.candidate_recall import drop_seen, sample_users


def test_candidate_metrics_report_macro_micro_size_and_catalog_coverage():
    result = candidate_retrieval_metrics(
        [[1, 2, 1], [4]],
        [{1, 3}, {4, 5}],
        catalog_size=6,
    )
    assert result == {
        "users": 2,
        "target_interactions": 4,
        "recall": pytest.approx(0.5),
        "hit_rate": 1.0,
        "candidate_coverage": 0.5,
        "mean_candidate_set_size": 1.5,
        "catalog_coverage": 0.5,
    }


def test_item_familiarity_metrics_separate_seen_and_unseen_targets():
    metrics = item_familiarity_metrics(
        [[0, 1], [4, 5]],
        [{0, 2}, {4, 5}],
        np.array([True, False, True, False, True, False]),
    )
    assert metrics["warm_item"]["candidate_coverage"] == pytest.approx(2 / 3)
    assert metrics["cold_item"]["candidate_coverage"] == pytest.approx(1.0)
    assert metrics["warm_item"]["users"] == 2
    assert metrics["cold_item"]["users"] == 1


def test_candidate_metrics_exclude_users_without_targets_and_handle_empty_groups():
    result = candidate_retrieval_metrics([[1], [2]], [{1}, set()], 3)
    assert result["users"] == 1
    assert result["recall"] == result["candidate_coverage"] == 1.0
    empty = candidate_retrieval_metrics([[]], [set()], 3)
    assert empty["users"] == 0 and empty["recall"] is None


def test_latency_summary_and_input_validation():
    assert latency_summary([0.1, 0.3]) == {
        "calls": 2,
        "total_seconds": pytest.approx(0.4),
        "mean_seconds": pytest.approx(0.2),
        "p50_seconds": pytest.approx(0.2),
        "p95_seconds": pytest.approx(0.29),
    }
    with pytest.raises(ValueError, match="same length"):
        candidate_retrieval_metrics([[1]], [], 2)
    with pytest.raises(ValueError, match="positive"):
        candidate_retrieval_metrics([], [], 0)
    with pytest.raises(ValueError, match="finite"):
        latency_summary([float("nan")])


def test_candidate_helpers_deduplicate_and_sample_deterministically():
    assert drop_seen([1, 1, 2, 3], {2}, 5) == [1, 3]
    segments = {0: "warm", 2: "warm", 1: "cold", 3: "cold"}
    first = sample_users(segments, 1, np.random.default_rng(7))
    second = sample_users(segments, 1, np.random.default_rng(7))
    assert first == second
    assert set(first) == {"cold", "sparse", "warm"}
    with pytest.raises(ValueError, match="positive"):
        sample_users(segments, 0, np.random.default_rng(0))
