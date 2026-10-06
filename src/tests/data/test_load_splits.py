import pandas as pd
import pytest

from package.data.split import infer_matrix_shape, load_splits


def _write(dir_, name, rows):
    pd.DataFrame(rows).to_parquet(dir_ / f"{name}.parquet", index=False)


def test_load_splits_returns_three_frames_and_skips_missing_columns(tmp_path):
    _write(tmp_path, "train", {"user_idx": [0, 1], "item_idx": [0, 2], "timestamp": [1, 2]})
    _write(tmp_path, "validation", {"user_idx": [1], "item_idx": [3], "timestamp": [3]})
    _write(tmp_path, "test", {"user_idx": [0], "item_idx": [1], "timestamp": [4]})

    train, val, test = load_splits(tmp_path)
    assert list(train.columns) == ["user_idx", "item_idx"]

    train, _, _ = load_splits(tmp_path, ("user_idx", "item_idx", "timestamp", "not_there"))
    assert list(train.columns) == ["user_idx", "item_idx", "timestamp"]
    assert infer_matrix_shape(train, val, test) == (2, 4)


def test_load_splits_missing_file_points_to_stage3(tmp_path):
    with pytest.raises(FileNotFoundError, match="stage3"):
        load_splits(tmp_path)
