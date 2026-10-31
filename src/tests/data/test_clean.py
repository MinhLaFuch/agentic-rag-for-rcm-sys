import gzip
import json

import pandas as pd
import pytest

from package.data.clean import clean_interactions, iter_reviews_dataframes, load_reviews_dataframe


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


def test_load_reviews_dataframe_with_column_subset(synthetic_review_file):
    df = load_reviews_dataframe(synthetic_review_file, columns=["user_id", "parent_asin"])
    assert list(df.columns) == ["user_id", "parent_asin"]


def test_load_reviews_dataframe_missing_column_raises(synthetic_review_file):
    with pytest.raises(ValueError):
        load_reviews_dataframe(synthetic_review_file, columns=["not_a_real_column"])


def test_iter_reviews_dataframes_reads_all_rows_in_chunks(synthetic_review_file):
    chunks = list(
        iter_reviews_dataframes(
            synthetic_review_file,
            columns=["user_id", "parent_asin"],
            chunksize=3,
        )
    )

    assert [len(chunk) for chunk in chunks] == [3, 1]
    assert all(list(chunk.columns) == ["user_id", "parent_asin"] for chunk in chunks)
    assert all(str(chunk["user_id"].dtype).startswith("string") for chunk in chunks)
    assert all(str(chunk["parent_asin"].dtype).startswith("string") for chunk in chunks)


def test_iter_reviews_dataframes_preserves_numeric_looking_item_ids(tmp_path):
    path = tmp_path / "ids.jsonl"
    path.write_text(
        '{"user_id":"u","parent_asin":"0486418189","rating":5,"timestamp":900000000000}\n'
        '{"user_id":"u","parent_asin":"B000000001","rating":5,"timestamp":900000000001}\n',
        encoding="utf-8",
    )
    chunks = list(iter_reviews_dataframes(path, chunksize=1))
    assert chunks[0].iloc[0]["parent_asin"] == "0486418189"
    assert chunks[1].iloc[0]["parent_asin"] == "B000000001"


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


def test_clean_interactions_validates_rating_and_millisecond_timestamp_and_keeps_last():
    df = pd.DataFrame(
        [
            ["u", "a", 3, 900000000000],
            ["u", "a", 5, 900000000000],  # last row wins for duplicate key
            ["u", "b", 0, 900000000000],
            ["u", "c", 6, 900000000000],
            ["u", "d", -1, 900000000000],
            ["u", "e", 4, 0],  # seconds/epoch value rejected by configured range
        ],
        columns=["user_id", "parent_asin", "rating", "timestamp"],
    )
    df["user_id"] = df["user_id"].astype("string")
    df["parent_asin"] = df["parent_asin"].astype("string")
    cleaned, report = clean_interactions(
        df, validate_values=True, min_timestamp_ms=788918400000, max_timestamp_ms=1704067200000,
        max_invalid_timestamp_fraction=1.0,
    )
    assert cleaned[["parent_asin", "rating"]].values.tolist() == [["a", 5]]
    assert report["num_dropped_invalid_rating"] == 3
    assert report["num_dropped_invalid_timestamp"] == 1
    assert report["num_dropped_duplicates"] == 1


def test_clean_interactions_timestamp_rate_gate_has_unit_hint():
    df = pd.DataFrame([["u", "a", 5, 1]], columns=["user_id", "parent_asin", "rating", "timestamp"])
    df["user_id"] = df["user_id"].astype("string")
    df["parent_asin"] = df["parent_asin"].astype("string")
    with pytest.raises(ValueError, match="possibly incorrect timestamp unit"):
        clean_interactions(df, validate_values=True, min_timestamp_ms=788918400000,
                           max_timestamp_ms=1704067200000, max_invalid_timestamp_fraction=0.0)
