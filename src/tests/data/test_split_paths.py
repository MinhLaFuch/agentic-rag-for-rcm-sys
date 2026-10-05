import pandas as pd
import pytest

from package.config import get_data_paths
from package.data.mapping import load_mappings, save_mappings
from package.data.mapping._schema import ITEM2ID_FILE, USER2ID_FILE
from package.data.split import load_splits, save_splits, split_path
from package.data.split._schema import SPLIT_NAMES


def test_split_path_is_the_single_naming_rule(tmp_path):
    assert [split_path(tmp_path, n).name for n in SPLIT_NAMES] == ["train.parquet", "validation.parquet", "test.parquet"]
    with pytest.raises(ValueError):
        split_path(tmp_path, "valid")  # typo must fail loudly, not silently create a new file name


def test_datapaths_split_path_matches_data_layer(tmp_path):
    paths = get_data_paths("t")
    for name in SPLIT_NAMES:
        assert paths.split_path(name) == split_path(paths.splits_dir, name)


def test_save_then_load_splits_roundtrip(tmp_path):
    frames = [pd.DataFrame({"user_idx": [i], "item_idx": [i + 1]}) for i in range(3)]
    out = save_splits(*frames, tmp_path / "nested" / "splits")  # creates the directory
    assert sorted(p.name for p in out.iterdir()) == sorted(f"{n}.parquet" for n in SPLIT_NAMES)
    train, val, test = load_splits(out)
    assert (train["user_idx"][0], val["user_idx"][0], test["user_idx"][0]) == (0, 1, 2)


def test_mapping_files_use_shared_names(tmp_path):
    save_mappings({"u": 0}, {"i": 0}, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([USER2ID_FILE, ITEM2ID_FILE])
    assert load_mappings(tmp_path) == ({"u": 0}, {"i": 0})
