import dataclasses
import json
import logging

import pandas as pd
import pytest

from package.data.save import (
    ExportDirs,
    ensure_dir,
    save_mappings,
    write_id_maps,
    write_jsonl,
    write_products,
    write_simulator_jsonl,
    write_splits,
)
from package.data.loader import load_mappings
from package.utils.path import WORKSPACE_ENV_VAR

CATEGORY = "All_Beauty"


@pytest.fixture
def synthetic_meta():
    return pd.DataFrame(
        {
            "item_id": ["A1", "A2", "A3", "A4", "A1"],  # A1 duplicated, A4 not in item_map
            "title": ["Alphabet", "Betamax", "Gammarays", "Deltaforce", "Alphabet v2"],
            "category": ["c"] * 5,
            "price": [1.0, 2.0, 3.0, 4.0, 5.0],
            "description": ["d"] * 5,
        }
    )


@pytest.fixture
def synthetic_item_map():
    # ids are the *mapped* ints, like the pipeline produces
    return {"A1": 0, "A2": 1, "A3": 2}


@pytest.fixture
def synthetic_history():
    # item 0 visited twice, item 1 once, item 2 never
    return pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u2"],
            "item_id": [0, 1, 0],
            "timestamp": [1, 2, 3],
        }
    )


@pytest.fixture
def synthetic_products():
    return pd.DataFrame({"id": [0, 1, 2], "title": ["Alphabet", "Betamax", "Gammarays"]})


@pytest.fixture
def synthetic_sim_history():
    # chronological: u1 -> [0, 1, 2], u2 -> [1]
    return pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u1", "u2"],
            "item_id": [2, 0, 1, 1],  # deliberately not in time order
            "timestamp": [3, 1, 2, 1],
        }
    )


@pytest.fixture
def synthetic_test_rows():
    return pd.DataFrame(
        {
            "user_id": ["u1", "u2", "u3"],  # u3 has no history
            "item_id": [1, 2, 0],
            "timestamp": [10, 11, 12],
        }
    )


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ------------------------------------------------------------ ensure_dir


def test_ensure_dir_creates_nested_and_returns_path(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    assert ensure_dir(target) == target
    assert target.is_dir()


def test_ensure_dir_is_idempotent(tmp_path):
    ensure_dir(tmp_path / "x")
    ensure_dir(tmp_path / "x")  # must not raise
    assert (tmp_path / "x").is_dir()


# ------------------------------------------------------------ ExportDirs


def test_export_dirs_layout(resource_root):
    dirs = ExportDirs(CATEGORY)
    assert dirs.mapped == resource_root / "local" / "mapped" / CATEGORY
    assert dirs.processed == resource_root / "local" / "processed" / CATEGORY
    assert dirs.splits == resource_root / "local" / "splits" / CATEGORY


def test_export_dirs_workspace_argument(resource_root):
    assert ExportDirs(CATEGORY, "recai").splits == resource_root / "recai" / "splits" / CATEGORY


def test_export_dirs_uses_env_workspace_when_none_given(resource_root, monkeypatch):
    monkeypatch.setenv(WORKSPACE_ENV_VAR, "recai")
    assert ExportDirs(CATEGORY).processed == resource_root / "recai" / "processed" / CATEGORY


def test_export_dirs_does_not_create_directories(resource_root):
    dirs = ExportDirs(CATEGORY)
    _ = (dirs.mapped, dirs.processed, dirs.splits)
    assert not (resource_root / "local").exists()


def test_export_dirs_rejects_shared_raw_workspace(resource_root):
    with pytest.raises(ValueError):
        ExportDirs(CATEGORY, "raw").mapped


def test_export_dirs_is_frozen_and_only_category_workspace_are_fields():
    dirs = ExportDirs(CATEGORY)
    with pytest.raises(dataclasses.FrozenInstanceError):
        dirs.category = "other"
    assert [f.name for f in dataclasses.fields(ExportDirs)] == ["category", "workspace"]
    assert (ExportDirs.MAPPED, ExportDirs.PROCESSED, ExportDirs.SPLITS) == ("mapped", "processed", "splits")


# ----------------------------------------------------------- write_jsonl


def test_write_jsonl_one_object_per_line(tmp_path):
    records = [{"a": 1}, {"a": 2, "b": [1, 2]}]
    path = tmp_path / "out.jsonl"
    write_jsonl(records, path)

    assert path.read_text(encoding="utf-8").count("\n") == 2
    assert read_jsonl(path) == records


def test_write_jsonl_keeps_unicode_unescaped(tmp_path):
    path = tmp_path / "out.jsonl"
    write_jsonl([{"title": "Kem dưỡng da"}], path)
    assert "Kem dưỡng da" in path.read_text(encoding="utf-8")


def test_write_jsonl_empty_list_writes_empty_file(tmp_path):
    path = tmp_path / "out.jsonl"
    write_jsonl([], path)
    assert path.read_text(encoding="utf-8") == ""


# ----------------------------------------------------------- write_id_maps


def test_write_id_maps_writes_item_and_user_under_mapped(resource_root):
    path = write_id_maps({"A1": 0}, {"u1": 0, "u2": 1}, CATEGORY)

    assert path == resource_root / "local" / "mapped" / CATEGORY / "map.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {"item": {"A1": 0}, "user": {"u1": 0, "u2": 1}}


def test_write_id_maps_workspace_and_logging(resource_root, caplog):
    with caplog.at_level(logging.INFO, logger="package.data.save.id_map"):
        path = write_id_maps({"A1": 0}, {"u1": 0}, CATEGORY, workspace="recai")
    assert path.parent == resource_root / "recai" / "mapped" / CATEGORY
    assert any("Wrote" in record.getMessage() for record in caplog.records)


# ----------------------------------------------------------- save_mappings


def test_save_mappings_writes_both_files_and_creates_dir(tmp_path):
    out = tmp_path / "new" / "dir"
    save_mappings({"u1": 0}, {"i1": 0, "i2": 1}, out)
    assert json.loads((out / "user2id.json").read_text(encoding="utf-8")) == {"u1": 0}
    assert json.loads((out / "item2id.json").read_text(encoding="utf-8")) == {"i1": 0, "i2": 1}


def test_save_mappings_roundtrips_with_loader_including_unicode(tmp_path):
    user2id = {"người dùng": 0, "u2": 1}
    item2id = {"sản phẩm": 0}
    save_mappings(user2id, item2id, str(tmp_path))
    assert load_mappings(tmp_path) == (user2id, item2id)


def test_save_mappings_logs_counts(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="package.data.save.map"):
        save_mappings({"u1": 0}, {"i1": 0, "i2": 1}, tmp_path)
    assert any("1 users, 2 items" in record.getMessage() for record in caplog.records)


# ------------------------------------------------------------ write_splits


def test_write_splits_writes_four_tsv_files(resource_root):
    train = pd.DataFrame({"user_id": ["u1", "u2"], "item_id": [0, 1]})
    valid = pd.DataFrame({"user_id": ["u1"], "item_id": [2]})
    test = pd.DataFrame({"user_id": ["u1"], "item_id": [3], "timestamp": [9]})
    history = pd.DataFrame({"user_id": ["u1"], "item_id": [0], "timestamp": [1]})

    out = write_splits(train, valid, test, history, CATEGORY)

    assert out == resource_root / "local" / "splits" / CATEGORY
    for name in ("train", "valid", "test", "user_history"):
        assert (out / f"{name}.tsv").exists()
    pd.testing.assert_frame_equal(pd.read_csv(out / "train.tsv"), train)
    pd.testing.assert_frame_equal(pd.read_csv(out / "test.tsv"), test)
    pd.testing.assert_frame_equal(pd.read_csv(out / "user_history.tsv"), history)


def test_write_splits_does_not_write_index_column(resource_root):
    frame = pd.DataFrame({"user_id": ["u1"], "item_id": [0]})
    out = write_splits(frame, frame, frame, frame, CATEGORY)
    assert (out / "train.tsv").read_text(encoding="utf-8").splitlines()[0] == "user_id,item_id"


def test_write_splits_workspace_and_logging(resource_root, caplog):
    frame = pd.DataFrame({"user_id": ["u1"], "item_id": [0]})
    with caplog.at_level(logging.INFO, logger="package.data.save.split"):
        out = write_splits(frame, frame, frame, frame, CATEGORY, workspace="recai")
    assert out == resource_root / "recai" / "splits" / CATEGORY
    assert any("Wrote splits" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------- write_products


def test_write_products_maps_ids_and_counts_visits(resource_root, synthetic_meta, synthetic_item_map, synthetic_history):
    products = write_products(synthetic_meta, synthetic_item_map, synthetic_history, CATEGORY)

    assert list(products.columns) == ["id", "title", "category", "price", "description", "visited_num"]
    by_id = products.set_index("id")
    assert by_id.loc[0, "visited_num"] == 2  # visited by u1 and u2
    assert by_id.loc[1, "visited_num"] == 1
    assert by_id.loc[2, "visited_num"] == 0  # never visited -> 0, not NaN
    assert products["visited_num"].dtype.kind == "i"


def test_write_products_drops_unmapped_items_and_duplicates(resource_root, synthetic_meta, synthetic_item_map, synthetic_history):
    products = write_products(synthetic_meta, synthetic_item_map, synthetic_history, CATEGORY)

    assert sorted(products["id"]) == [0, 1, 2]  # A4 (not in item_map) is gone, A1 only once
    assert products.set_index("id").loc[0, "title"] == "Alphabet"  # first duplicate kept
    assert list(products.index) == [0, 1, 2]


def test_write_products_writes_feather_and_pipe_csv(resource_root, synthetic_meta, synthetic_item_map, synthetic_history):
    pytest.importorskip("pyarrow")
    products = write_products(synthetic_meta, synthetic_item_map, synthetic_history, CATEGORY)

    out = resource_root / "local" / "processed" / CATEGORY
    pd.testing.assert_frame_equal(pd.read_feather(out / "products.ftr"), products)
    pd.testing.assert_frame_equal(pd.read_csv(out / "products.csv", sep="|"), products)


def test_write_products_workspace_and_logging(resource_root, synthetic_meta, synthetic_item_map, synthetic_history, caplog):
    pytest.importorskip("pyarrow")
    with caplog.at_level(logging.INFO, logger="package.data.save.product"):
        write_products(synthetic_meta, synthetic_item_map, synthetic_history, CATEGORY, workspace="recai")
    assert (resource_root / "recai" / "processed" / CATEGORY / "products.csv").exists()
    assert any("Wrote 3 products" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------- write_simulator_jsonl


def test_write_simulator_jsonl_builds_history_and_target(resource_root, synthetic_test_rows, synthetic_sim_history, synthetic_products):
    path = write_simulator_jsonl(synthetic_test_rows, synthetic_sim_history, synthetic_products, CATEGORY)

    assert path == resource_root / "local" / "processed" / CATEGORY / "simulator_test_data_3.jsonl"
    by_target = {row["target"]: row["history"] for row in read_jsonl(path)}
    assert by_target == {
        "Betamax": "Alphabet; Betamax; Gammarays",  # u1: chronological, even though rows were shuffled
        "Gammarays": "Betamax",  # u2
        "Alphabet": "",  # u3: no history -> empty string
    }


def test_write_simulator_jsonl_rows_have_only_history_and_target(resource_root, synthetic_test_rows, synthetic_sim_history, synthetic_products):
    path = write_simulator_jsonl(synthetic_test_rows, synthetic_sim_history, synthetic_products, CATEGORY)
    assert all(set(row) == {"history", "target"} for row in read_jsonl(path))


def test_write_simulator_jsonl_sample_n_limits_rows_and_names_file(resource_root, synthetic_test_rows, synthetic_sim_history, synthetic_products):
    path = write_simulator_jsonl(synthetic_test_rows, synthetic_sim_history, synthetic_products, CATEGORY, sample_n=2)
    assert path.name == "simulator_test_data_2.jsonl"
    assert len(read_jsonl(path)) == 2


def test_write_simulator_jsonl_sample_n_is_capped_at_test_size(resource_root, synthetic_test_rows, synthetic_sim_history, synthetic_products):
    path = write_simulator_jsonl(synthetic_test_rows, synthetic_sim_history, synthetic_products, CATEGORY, sample_n=900)
    assert path.name == "simulator_test_data_3.jsonl"


def test_write_simulator_jsonl_same_seed_is_deterministic(resource_root, synthetic_test_rows, synthetic_sim_history, synthetic_products):
    first = write_simulator_jsonl(synthetic_test_rows, synthetic_sim_history, synthetic_products, CATEGORY, sample_n=2, seed=7)
    first_text = first.read_text(encoding="utf-8")
    second = write_simulator_jsonl(synthetic_test_rows, synthetic_sim_history, synthetic_products, CATEGORY, sample_n=2, seed=7)
    assert second.read_text(encoding="utf-8") == first_text


def test_write_simulator_jsonl_max_history_len_keeps_most_recent(resource_root, synthetic_test_rows, synthetic_sim_history, synthetic_products):
    path = write_simulator_jsonl(synthetic_test_rows, synthetic_sim_history, synthetic_products, CATEGORY, max_history_len=2)
    by_target = {row["target"]: row["history"] for row in read_jsonl(path)}
    assert by_target["Betamax"] == "Betamax; Gammarays"


def test_write_simulator_jsonl_max_title_len_truncates_history_titles(resource_root, synthetic_test_rows, synthetic_sim_history, synthetic_products):
    path = write_simulator_jsonl(synthetic_test_rows, synthetic_sim_history, synthetic_products, CATEGORY, max_title_len=4)
    by_target = {row["target"]: row["history"] for row in read_jsonl(path)}
    assert by_target["Betamax"] == "Alph; Beta; Gamm"


def test_write_simulator_jsonl_keeps_unicode_titles(resource_root, synthetic_sim_history):
    products = pd.DataFrame({"id": [0, 1, 2], "title": ["Kem dưỡng da", "B", "C"]})
    test = pd.DataFrame({"user_id": ["u2"], "item_id": [0], "timestamp": [5]})
    path = write_simulator_jsonl(test, synthetic_sim_history, products, CATEGORY)
    assert "Kem dưỡng da" in path.read_text(encoding="utf-8")


def test_write_simulator_jsonl_workspace_and_logging(resource_root, synthetic_test_rows, synthetic_sim_history, synthetic_products, caplog):
    with caplog.at_level(logging.INFO, logger="package.data.save.simulation"):
        path = write_simulator_jsonl(
            synthetic_test_rows, synthetic_sim_history, synthetic_products, CATEGORY, workspace="recai"
        )
    assert path.parent == resource_root / "recai" / "processed" / CATEGORY
    assert any("simulator rows" in record.getMessage() for record in caplog.records)