import gzip
import json

import pandas as pd
import pytest

from src.data.clean import clean_interactions, load_reviews_dataframe


@pytest.fixture
def synthetic_review_file(tmp_path):
    rows = [
        {"user_id": "u1", "parent_asin": "i1", "rating": 5.0, "timestamp": 100, "title": "t1"},
        {"user_id": "u1", "parent_asin": "i1", "rating": 5.0, "timestamp": 100, "title": "t1_dup"},  # duplicate key
        {"user_id": "u2", "parent_asin": "i2", "rating": None, "timestamp": 200, "title": "t2"},  # missing rating
        {"user_id": "u3", "parent_asin": "i1", "rating": 3.0, "timestamp": 300, "title": "t3"},
    ]
    path = tmp_path / "review_test.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def test_load_reviews_dataframe_reads_all_rows(synthetic_review_file):
    df = load_reviews_dataframe(synthetic_review_file)
    assert len(df) == 4
    assert set(["user_id", "parent_asin", "rating", "timestamp"]).issubset(df.columns)
    assert pd.api.types.is_integer_dtype(df["timestamp"])


def test_load_reviews_dataframe_with_column_subset(synthetic_review_file):
    df = load_reviews_dataframe(synthetic_review_file, columns=["user_id", "parent_asin"])
    assert list(df.columns) == ["user_id", "parent_asin"]


def test_load_reviews_dataframe_missing_column_raises(synthetic_review_file):
    with pytest.raises(ValueError):
        load_reviews_dataframe(synthetic_review_file, columns=["not_a_real_column"])


def test_clean_interactions_drops_missing_and_duplicates(synthetic_review_file):
    df = load_reviews_dataframe(synthetic_review_file)
    cleaned, report = clean_interactions(df)

    assert report["num_input"] == 4
    assert report["num_dropped_missing_required_fields"] == 1  # u2 missing rating
    assert report["num_dropped_duplicates"] == 1  # duplicate (u1, i1, 100)
    assert report["num_output"] == 2
    assert len(cleaned) == 2


def test_clean_interactions_raises_on_missing_required_columns():
    bad_df = pd.DataFrame({"user_id": ["u1"], "parent_asin": ["i1"]})
    with pytest.raises(ValueError):
        clean_interactions(bad_df)
