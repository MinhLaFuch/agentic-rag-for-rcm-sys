import dataclasses
import gzip
import inspect
import json
import logging

import pandas as pd
import pytest

from package.data.utils import (
    REVIEW_SCHEMA,
    ColumnSchema,
    list_categories,
    open_jsonl,
    parse_list,
    read_cached_jsonl,
    resolve_category,
)
from package.data.utils._helper import _tokens


@pytest.fixture
def synthetic_raw_dir(resource_root):
    raw = resource_root / "raw"
    for name in ("All_Beauty", "Luxury_Beauty", "Video_Games"):
        (raw / name).mkdir(parents=True)
    (raw / "stray_file.txt").touch()  # files must be ignored
    return raw


@pytest.fixture
def synthetic_meta_records():
    return [
        {"parent_asin": "A1", "title": "One", "description": ["d1", "d2"], "price": 1.5},
        {"parent_asin": "A2", "title": "Two", "description": [], "price": None},
    ]


# ------------------------------------------------------ ColumnSchema


def test_review_schema_required_columns():
    assert REVIEW_SCHEMA.required == ("user_id", "parent_asin", "rating", "timestamp")


def test_review_schema_all_is_required_plus_optional_without_duplicates():
    assert REVIEW_SCHEMA.all == REVIEW_SCHEMA.required + REVIEW_SCHEMA.optional
    assert len(set(REVIEW_SCHEMA.all)) == len(REVIEW_SCHEMA.all)


def test_column_schema_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        REVIEW_SCHEMA.required = ("x",)


def test_column_schema_accepts_custom_columns():
    schema = ColumnSchema(required=("a",), optional=("b", "c"))
    assert schema.all == ("a", "b", "c")


# --------------------------------------------------------- parse_list


@pytest.mark.parametrize(
    "value, expected",
    [
        (["a", "b"], ["a", "b"]),  # already a list -> untouched
        ("['a', 'b']", ["a", "b"]),  # what the tsv cache stores
        ("[1, 2]", [1, 2]),
        ("[]", []),
        ("['unclosed'", []),  # syntax error -> []
        ("[x for x in y]", []),  # not a literal -> []
        ("plain text", []),
        ("", []),
        (None, []),
        (float("nan"), []),  # NaN from pandas
        (("a", "b"), []),  # tuples are not accepted
    ],
)
def test_parse_list_handles_every_input_shape(value, expected):
    assert parse_list(value) == expected


# --------------------------------------------------------- open_jsonl


def test_open_jsonl_yields_records(tmp_path, write_jsonl_gz):
    records = [{"a": 1}, {"a": 2, "b": "x"}]
    path = write_jsonl_gz(tmp_path / "data.jsonl.gz", records)
    assert list(open_jsonl(path)) == records


def test_open_jsonl_is_lazy(tmp_path, write_jsonl_gz):
    path = write_jsonl_gz(tmp_path / "data.jsonl.gz", [{"a": 1}])
    assert inspect.isgenerator(open_jsonl(path))


def test_open_jsonl_skips_blank_lines(tmp_path):
    path = tmp_path / "data.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write('{"a": 1}\n\n   \n{"a": 2}\n')
    assert list(open_jsonl(path)) == [{"a": 1}, {"a": 2}]


def test_open_jsonl_reads_unicode(tmp_path, write_jsonl_gz):
    path = write_jsonl_gz(tmp_path / "data.jsonl.gz", [{"title": "Kem dưỡng da"}])
    assert next(open_jsonl(path))["title"] == "Kem dưỡng da"


def test_open_jsonl_empty_file_yields_nothing(tmp_path, write_jsonl_gz):
    path = write_jsonl_gz(tmp_path / "empty.jsonl.gz", [])
    assert list(open_jsonl(path)) == []


def test_open_jsonl_malformed_line_raises(tmp_path):
    path = tmp_path / "bad.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write("not json\n")
    with pytest.raises(json.JSONDecodeError):
        list(open_jsonl(path))


def test_open_jsonl_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        list(open_jsonl(tmp_path / "missing.jsonl.gz"))


def test_open_jsonl_is_gzip_only(tmp_path):
    path = tmp_path / "plain.jsonl"
    path.write_text('{"a": 1}\n', encoding="utf-8")
    with pytest.raises(OSError):  # gzip.BadGzipFile
        list(open_jsonl(path))


# ------------------------------------------------------ list_categories


def test_list_categories_returns_sorted_folder_names_only(synthetic_raw_dir):
    assert list_categories() == ["All_Beauty", "Luxury_Beauty", "Video_Games"]


def test_list_categories_explicit_root(tmp_path):
    (tmp_path / "b").mkdir()
    (tmp_path / "a").mkdir()
    assert list_categories(tmp_path) == ["a", "b"]


def test_list_categories_empty_root(tmp_path):
    assert list_categories(tmp_path) == []


def test_list_categories_missing_root_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="Raw data directory not found"):
        list_categories(tmp_path / "nope")


# ----------------------------------------------------- resolve_category


@pytest.mark.parametrize("query", ["video games", "Video_Games", "video-games", "VIDEO GAMES", "games video"])
def test_resolve_category_exact_match_ignores_case_separators_and_order(synthetic_raw_dir, query):
    assert resolve_category(query) == "Video_Games"


def test_resolve_category_partial_match(synthetic_raw_dir):
    assert resolve_category("games") == "Video_Games"
    assert resolve_category("all") == "All_Beauty"


def test_resolve_category_exact_beats_partial(synthetic_raw_dir):
    (synthetic_raw_dir / "Video_Games_Retro").mkdir()
    assert resolve_category("video games") == "Video_Games"


def test_resolve_category_ambiguous_raises(synthetic_raw_dir):
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_category("beauty")


def test_resolve_category_no_match_raises_and_lists_available(synthetic_raw_dir):
    with pytest.raises(ValueError, match="No category matches") as excinfo:
        resolve_category("toys")
    assert "All_Beauty" in str(excinfo.value)


@pytest.mark.parametrize("query", ["", "   ", "___", "--"])
def test_resolve_category_empty_query_raises(synthetic_raw_dir, query):
    with pytest.raises(ValueError, match="must not be empty"):
        resolve_category(query)


# ------------------------------------------------- read_cached_jsonl


def test_read_cached_jsonl_parses_source_and_writes_pipe_cache(tmp_path, write_jsonl_gz, synthetic_meta_records):
    source = write_jsonl_gz(tmp_path / "meta.jsonl.gz", synthetic_meta_records)
    cache = tmp_path / "cache" / "meta.tsv"  # parent dir does not exist yet

    frame = read_cached_jsonl(source, cache)

    assert list(frame["parent_asin"]) == ["A1", "A2"]
    assert cache.exists()
    assert cache.read_text(encoding="utf-8").splitlines()[0].count("|") == frame.shape[1] - 1


def test_read_cached_jsonl_uses_cache_and_never_touches_source(tmp_path, write_jsonl_gz, synthetic_meta_records):
    source = write_jsonl_gz(tmp_path / "meta.jsonl.gz", synthetic_meta_records)
    cache = tmp_path / "meta.tsv"
    first = read_cached_jsonl(source, cache)

    source.unlink()  # a cache hit must not need the source
    second = read_cached_jsonl(source, cache)

    assert list(second["parent_asin"]) == list(first["parent_asin"])
    assert list(second["title"]) == list(first["title"])


def test_read_cached_jsonl_cache_turns_lists_into_strings_that_parse_list_recovers(
    tmp_path, write_jsonl_gz, synthetic_meta_records
):
    source = write_jsonl_gz(tmp_path / "meta.jsonl.gz", synthetic_meta_records)
    cache = tmp_path / "meta.tsv"

    fresh = read_cached_jsonl(source, cache)
    cached = read_cached_jsonl(source, cache)

    assert fresh["description"][0] == ["d1", "d2"]
    assert isinstance(cached["description"][0], str)
    assert parse_list(cached["description"][0]) == ["d1", "d2"]


def test_read_cached_jsonl_logs_hit_and_miss(tmp_path, write_jsonl_gz, synthetic_meta_records, caplog):
    source = write_jsonl_gz(tmp_path / "meta.jsonl.gz", synthetic_meta_records)
    cache = tmp_path / "meta.tsv"

    with caplog.at_level(logging.INFO, logger="package.data.utils.read_cached_jsonl"):
        read_cached_jsonl(source, cache)
        read_cached_jsonl(source, cache)

    messages = [record.getMessage() for record in caplog.records]
    assert any("No cache found" in m for m in messages)
    assert any("Loading cached data" in m for m in messages)


# ------------------------------------------------------------- _tokens


@pytest.mark.parametrize("text", ["All_Beauty", "all beauty", "all-beauty", "ALL  BEAUTY", "beauty all"])
def test_tokens_normalizes_case_and_separators(text):
    assert _tokens(text) == {"all", "beauty"}


def test_tokens_keeps_digits_and_collapses_duplicates():
    assert _tokens("Home_2_Home") == {"home", "2"}


def test_tokens_empty_when_no_alphanumerics():
    assert _tokens("___ --") == set()
