import json
import logging

import pandas as pd
import pytest

from package.data.loader import join_description, load_mappings, load_reviews_and_metadata


@pytest.fixture
def synthetic_category(resource_root, write_jsonl_gz):
    """resource/raw/All_Beauty with a review file and a meta file that exercise every cleaning rule."""
    raw = resource_root / "raw" / "All_Beauty"
    write_jsonl_gz(
        raw / "meta_All_Beauty.jsonl.gz",
        [
            {"parent_asin": "A1", "title": "Shampoo", "description": ["d1", "d2", "d3"],
             "categories": ["Beauty", "Hair"], "price": 9.99},
            {"parent_asin": "A2", "title": None, "description": ["x"],
             "categories": ["Beauty"], "price": 1.0},  # no title -> item dropped
            {"parent_asin": "A3", "title": "Soap", "description": [],
             "categories": [], "price": None},  # empty description / categories
            {"parent_asin": "A1", "title": "Shampoo v2", "description": ["dup"],
             "categories": ["Other"], "price": 5.0},  # duplicate item -> first kept
        ],
    )
    write_jsonl_gz(
        raw / "All_Beauty.jsonl.gz",
        [
            {"user_id": "u1", "parent_asin": "A1", "rating": 5, "timestamp": 100, "text": "great"},
            {"user_id": "u1", "parent_asin": "A2", "rating": 4, "timestamp": 200, "text": "no title item"},
            {"user_id": "u2", "parent_asin": "A3", "rating": 3, "timestamp": 300, "text": "ok"},
            {"user_id": "u3", "parent_asin": "A9", "rating": 2, "timestamp": 400, "text": "not in meta"},
        ],
    )
    return raw


# ------------------------------------------------------ join_description


@pytest.mark.parametrize(
    "value, expected",
    [
        (["one", "two", "three"], "one two"),  # default: first 2 sentences
        (["only"], "only"),
        ("['one', 'two', 'three']", "one two"),  # stringified list from the tsv cache
        ([1, 2, 3], "1 2"),  # non-strings are coerced
        ([], "No description"),
        (None, "No description"),
        (float("nan"), "No description"),
        ("just a sentence", "No description"),  # not a list -> nothing to join
    ],
)
def test_join_description_default(value, expected):
    assert join_description(value) == expected


def test_join_description_respects_max_sentences():
    assert join_description(["a", "b", "c"], max_sentences=1) == "a"
    assert join_description(["a", "b", "c"], max_sentences=3) == "a b c"
    assert join_description(["a", "b"], max_sentences=10) == "a b"


def test_join_description_zero_sentences_falls_back():
    assert join_description(["a", "b"], max_sentences=0) == "No description"


# --------------------------------------------------------- load_mappings


def test_load_mappings_reads_both_files(tmp_path):
    (tmp_path / "user2id.json").write_text(json.dumps({"u1": 0, "u2": 1}), encoding="utf-8")
    (tmp_path / "item2id.json").write_text(json.dumps({"i1": 0}), encoding="utf-8")

    user2id, item2id = load_mappings(tmp_path)

    assert user2id == {"u1": 0, "u2": 1}
    assert item2id == {"i1": 0}


def test_load_mappings_accepts_str_path_and_unicode(tmp_path):
    (tmp_path / "user2id.json").write_text(json.dumps({"người dùng": 0}, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "item2id.json").write_text(json.dumps({"sản phẩm": 0}, ensure_ascii=False), encoding="utf-8")

    user2id, item2id = load_mappings(str(tmp_path))

    assert user2id == {"người dùng": 0}
    assert item2id == {"sản phẩm": 0}


def test_load_mappings_missing_file_raises(tmp_path):
    (tmp_path / "user2id.json").write_text("{}", encoding="utf-8")  # item2id.json missing
    with pytest.raises(FileNotFoundError):
        load_mappings(tmp_path)


# ------------------------------------------- load_reviews_and_metadata


def test_load_reviews_and_metadata_output_columns(synthetic_category):
    reviews, meta = load_reviews_and_metadata("All_Beauty")
    assert list(reviews.columns) == ["user_id", "item_id", "rating", "timestamp"]
    assert list(meta.columns) == ["item_id", "title", "category", "price", "description"]


def test_load_reviews_and_metadata_drops_items_without_title_and_duplicates(synthetic_category):
    _, meta = load_reviews_and_metadata("All_Beauty")
    assert list(meta["item_id"]) == ["A1", "A3"]  # A2 has no title; second A1 dropped
    assert meta.loc[meta["item_id"] == "A1", "title"].item() == "Shampoo"  # first one kept


def test_load_reviews_and_metadata_keeps_only_reviews_of_surviving_items(synthetic_category):
    reviews, meta = load_reviews_and_metadata("All_Beauty")
    assert set(reviews["item_id"]) <= set(meta["item_id"])
    assert list(reviews["item_id"]) == ["A1", "A3"]  # A2 (no title) and A9 (not in meta) removed
    assert "text" not in reviews.columns  # only the required columns survive


def test_load_reviews_and_metadata_joins_description(synthetic_category):
    _, meta = load_reviews_and_metadata("All_Beauty")
    by_item = meta.set_index("item_id")
    assert by_item.loc["A1", "description"] == "d1 d2"
    assert by_item.loc["A3", "description"] == "No description"


def test_load_reviews_and_metadata_max_description_sentences(synthetic_category):
    _, meta = load_reviews_and_metadata("All_Beauty", max_description_sentences=1)
    assert meta.set_index("item_id").loc["A1", "description"] == "d1"


def test_load_reviews_and_metadata_takes_first_category(synthetic_category):
    _, meta = load_reviews_and_metadata("All_Beauty")
    by_item = meta.set_index("item_id")
    assert by_item.loc["A1", "category"] == "Beauty"
    assert by_item.loc["A3", "category"] == "Unknown"


def test_load_reviews_and_metadata_resets_index(synthetic_category):
    reviews, meta = load_reviews_and_metadata("All_Beauty")
    assert list(reviews.index) == list(range(len(reviews)))
    assert list(meta.index) == list(range(len(meta)))


def test_load_reviews_and_metadata_resolves_fuzzy_category_name(synthetic_category):
    reviews, _ = load_reviews_and_metadata("beauty")
    assert len(reviews) == 2


def test_load_reviews_and_metadata_writes_tsv_cache_and_second_call_matches(synthetic_category):
    first_reviews, first_meta = load_reviews_and_metadata("All_Beauty")
    assert (synthetic_category / "reviews.tsv").exists()
    assert (synthetic_category / "meta.tsv").exists()

    second_reviews, second_meta = load_reviews_and_metadata("All_Beauty")  # served from the cache

    pd.testing.assert_frame_equal(first_reviews, second_reviews)
    pd.testing.assert_frame_equal(first_meta, second_meta)


def test_load_reviews_and_metadata_handles_meta_without_description_or_categories(resource_root, write_jsonl_gz):
    raw = resource_root / "raw" / "All_Beauty"
    write_jsonl_gz(raw / "meta_All_Beauty.jsonl.gz", [{"parent_asin": "A1", "title": "Bare", "price": 1.0}])
    write_jsonl_gz(
        raw / "All_Beauty.jsonl.gz",
        [{"user_id": "u1", "parent_asin": "A1", "rating": 5, "timestamp": 1}],
    )

    _, meta = load_reviews_and_metadata("All_Beauty")

    assert meta.loc[0, "description"] == "No description"
    assert meta.loc[0, "category"] == "Unknown"


def test_load_reviews_and_metadata_unknown_category_raises(synthetic_category):
    with pytest.raises(ValueError, match="No category matches"):
        load_reviews_and_metadata("toys")


@pytest.mark.parametrize("missing", ["All_Beauty.jsonl.gz", "meta_All_Beauty.jsonl.gz"])
def test_load_reviews_and_metadata_missing_file_raises(synthetic_category, missing):
    (synthetic_category / missing).unlink()
    with pytest.raises(FileNotFoundError, match="Missing file for category"):
        load_reviews_and_metadata("All_Beauty")


def test_load_reviews_and_metadata_missing_required_review_column_raises(resource_root, write_jsonl_gz):
    raw = resource_root / "raw" / "All_Beauty"
    write_jsonl_gz(raw / "meta_All_Beauty.jsonl.gz", [{"parent_asin": "A1", "title": "T", "price": 1.0}])
    write_jsonl_gz(raw / "All_Beauty.jsonl.gz", [{"user_id": "u1", "parent_asin": "A1", "timestamp": 1}])  # no rating

    with pytest.raises(KeyError):
        load_reviews_and_metadata("All_Beauty")


def test_load_reviews_and_metadata_logs_shapes(synthetic_category, caplog):
    with caplog.at_level(logging.INFO, logger="package.data.loader.review_meta"):
        load_reviews_and_metadata("All_Beauty")
    assert any("Loaded All_Beauty" in record.getMessage() for record in caplog.records)
