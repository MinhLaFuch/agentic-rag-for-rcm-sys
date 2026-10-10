import numpy as np
import pandas as pd
import pytest

from package.tools.corpus import build_corpus
from package.tools.evaluation import segment_users, select_fit_target


def _frames():
    mk = lambda ts: pd.DataFrame({"user_idx": [0], "item_idx": [0], "timestamp": [ts]})
    return mk(1), mk(2), mk(3)


def test_select_fit_target_validation_uses_train_only():
    train, val, test = _frames()
    fit, target = select_fit_target(train, val, test, "validation")
    assert fit is train and target is val


def test_select_fit_target_test_adds_validation_to_fit():
    train, val, test = _frames()
    fit, target = select_fit_target(train, val, test, "test")
    assert sorted(fit["timestamp"]) == [1, 2] and target is test


def test_select_fit_target_rejects_unknown_split():
    with pytest.raises(ValueError):
        select_fit_target(*_frames(), "train")


def test_segment_users_thresholds():
    sizes = np.array([0, 2, 4, 5])
    assert segment_users([0, 1, 2, 3], sizes, sparse_max=4) == {0: "cold", 1: "sparse", 2: "sparse", 3: "warm"}


def test_build_corpus_raises_when_coverage_too_low(tmp_path):
    with pytest.raises(ValueError):
        build_corpus([], {"Video_Games::a": 0}, True, 0.5)
