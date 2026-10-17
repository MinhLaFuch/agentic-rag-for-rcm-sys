import numpy as np
import pandas as pd
import pytest

from package.tools.corpus import build_corpus
from package.tools.evaluation import segment_users_by_history, select_fit_target, parameter_grid


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


def test_segment_users_rejects_invalid_sparse_max():
    sizes = np.array([0, 2, 4, 5])
    with pytest.raises(ValueError, match="sparse_max must be a non-negative integer"):
        segment_users([0, 1, 2, 3], sizes, sparse_max=-1)

    with pytest.raises(ValueError, match="sparse_max must be a non-negative integer"):
        segment_users([0, 1, 2, 3], sizes, sparse_max=3.5)


def test_segment_users_rejects_out_of_bounds_user_indices():
    sizes = np.array([0, 2, 4, 5])
    with pytest.raises(ValueError, match="out of bounds"):
        segment_users([0, 1, 2, 10], sizes, sparse_max=4)

    with pytest.raises(ValueError, match="non-negative"):
        segment_users([-1, 0, 1, 2], sizes, sparse_max=4)


def test_segment_users_rejects_non_array_history_sizes():
    with pytest.raises(TypeError, match="history_sizes must be a numpy array"):
        segment_users([0, 1, 2], [0, 2, 4], sparse_max=4)


def test_build_corpus_raises_when_coverage_too_low(tmp_path):
    with pytest.raises(ValueError):
        build_corpus([], {"Video_Games::a": 0}, 0.5)


def test_parameter_grid_expands_combinations():
    grid = {"param1": [1, 2], "param2": ["a", "b"]}
    result = parameter_grid(grid)
    assert len(result) == 4
    assert {"param1": 1, "param2": "a"} in result
    assert {"param1": 1, "param2": "b"} in result
    assert {"param1": 2, "param2": "a"} in result
    assert {"param1": 2, "param2": "b"} in result


def test_parameter_grid_empty_grid():
    assert parameter_grid({}) == [{}]


def test_parameter_grid_rejects_non_dict():
    with pytest.raises(TypeError, match="grid must be a dictionary"):
        parameter_grid([1, 2, 3])


def test_parameter_grid_rejects_non_list_values():
    with pytest.raises(TypeError, match="must have a list of candidate values"):
        parameter_grid({"param1": "not_a_list"})

    with pytest.raises(TypeError, match="must have a list of candidate values"):
        parameter_grid({"param1": 123})


def test_parameter_grid_rejects_empty_list():
    with pytest.raises(ValueError, match="at least one candidate value"):
        parameter_grid({"param1": []})
