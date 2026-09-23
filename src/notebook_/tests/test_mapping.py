import pandas as pd
import pytest

from package.data.train.mapping import (
    apply_id_mapping,
    build_id_mappings,
    load_mappings,
    save_mappings,
)


@pytest.fixture
def synthetic_interactions():
    return pd.DataFrame(
        {
            "user_id": ["u1", "u2", "u1", "u3"],
            "parent_asin": ["i1", "i2", "i2", "i1"],
        }
    )


def test_build_id_mappings_unique_and_contiguous(synthetic_interactions):
    user2id, item2id = build_id_mappings(synthetic_interactions)

    assert set(user2id.keys()) == {"u1", "u2", "u3"}
    assert set(item2id.keys()) == {"i1", "i2"}
    assert sorted(user2id.values()) == [0, 1, 2]
    assert sorted(item2id.values()) == [0, 1]


def test_apply_id_mapping_adds_correct_columns(synthetic_interactions):
    user2id, item2id = build_id_mappings(synthetic_interactions)
    mapped = apply_id_mapping(synthetic_interactions, user2id, item2id)

    assert "user_idx" in mapped.columns
    assert "item_idx" in mapped.columns
    for _, row in mapped.iterrows():
        assert row["user_idx"] == user2id[row["user_id"]]
        assert row["item_idx"] == item2id[row["parent_asin"]]


def test_apply_id_mapping_raises_on_unknown_id(synthetic_interactions):
    user2id, item2id = build_id_mappings(synthetic_interactions)
    new_row = pd.DataFrame({"user_id": ["u_unknown"], "parent_asin": ["i1"]})
    with pytest.raises(ValueError):
        apply_id_mapping(new_row, user2id, item2id)


def test_save_and_load_mappings_roundtrip(tmp_path, synthetic_interactions):
    user2id, item2id = build_id_mappings(synthetic_interactions)
    save_mappings(user2id, item2id, tmp_path)
    loaded_user2id, loaded_item2id = load_mappings(tmp_path)

    assert loaded_user2id == user2id
    assert loaded_item2id == item2id
