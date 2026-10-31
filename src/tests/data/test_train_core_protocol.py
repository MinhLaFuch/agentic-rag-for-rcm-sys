from __future__ import annotations

import pandas as pd
from scipy.sparse import csr_matrix

from package.data.pipeline.prepare_train_core import prepare_train_core
from package.data.pipeline.build_evaluation_cohort import build_evaluation_cohort
from package.data.leakage import LeakageError, check_fit_core_subset
from package.data.split.temporal_split import temporal_split
import pytest


def _events(rows):
    return pd.DataFrame(rows, columns=["user_id", "parent_asin", "timestamp", "domain"])


def test_item_seen_only_in_test_is_excluded_from_train_core():
    train = _events(
        [(f"u{u}", f"item{i % 2}", u * 10 + i + 1, "Video_Games")
         for u in range(5) for i in range(5)]
    )
    test_only = _events([(f"t{i}", "test-only-item", 100 + i, "Video_Games") for i in range(5)])

    train_split, _, test_split = temporal_split(pd.concat([train, test_only]), 50, 75)
    assert len(test_split) == 5
    result = prepare_train_core(train_split, min_user_interactions=5, min_item_interactions=5)

    assert "test-only-item" not in set(result.core["parent_asin"])
    check_fit_core_subset(train, result.core)
    invalid = pd.concat([result.core, test_only.iloc[[0]]], ignore_index=True)
    with pytest.raises(LeakageError, match="absent from train"):
        check_fit_core_subset(train, invalid)
    assert len(test_only) == 5  # holdout data is intentionally not an input to fit-core


def test_fit_artifacts_do_not_depend_on_validation_or_test_rows():
    train = _events(
        [(f"u{u}", f"i{i % 2}", u * 10 + i + 1, "Video_Games")
         for u in range(2) for i in range(5)]
    )
    changed_holdout_a = _events([("v1", "val-a", 20, "Video_Games"), ("t1", "test-a", 30, "Video_Games")])
    changed_holdout_b = _events([("v9", "val-b", 22, "Video_Games"), ("t9", "test-b", 32, "Video_Games")])
    train_a, val_a, test_a = temporal_split(pd.concat([train, changed_holdout_a]), 15, 25)
    train_b, val_b, test_b = temporal_split(pd.concat([train, changed_holdout_b]), 15, 25)
    assert not val_a.equals(val_b) and not test_a.equals(test_b)
    result_a = prepare_train_core(train_a, 2, 2)
    result_b = prepare_train_core(train_b, 2, 2)

    pd.testing.assert_frame_equal(result_a.core, result_b.core)
    assert result_a.user2id == result_b.user2id
    assert result_a.item2id == result_b.item2id
    matrix_a = csr_matrix((
        [1] * len(result_a.core),
        (result_a.core.user_idx, result_a.core.item_idx),
    ), shape=(len(result_a.user2id), len(result_a.item2id)))
    matrix_b = csr_matrix((
        [1] * len(result_b.core),
        (result_b.core.user_idx, result_b.core.item_idx),
    ), shape=(len(result_b.user2id), len(result_b.item2id)))
    assert (matrix_a != matrix_b).nnz == 0
    assert changed_holdout_a.iloc[0].parent_asin != changed_holdout_b.iloc[0].parent_asin


def test_cohort_segment_rule_keeps_cold_users():
    train = _events([("warm", f"i{i}", i + 1, "Video_Games") for i in range(5)])
    targets = _events([("cold", "target-cold", 100, "Video_Games"),
                       ("warm", "target-warm", 101, "Video_Games")])
    cohort = build_evaluation_cohort(train, targets, sparse_max=4)

    assert cohort.set_index("user_id").loc["cold", "segment"] == "cold"
    assert cohort.set_index("user_id").loc["warm", "segment"] == "warm"
