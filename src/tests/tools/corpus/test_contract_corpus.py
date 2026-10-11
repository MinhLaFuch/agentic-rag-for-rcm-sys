"""Contract tests for ItemCorpus: ids, domains, categories, numeric columns, read-only protection."""

import gzip
import json
import warnings

import pandas as pd
import pytest

from package.tools import ItemCorpus, QueryTool
from package.tools.base import ToolInputError
from package.tools.corpus import build_corpus


def _df(**extra):
    base = {"parent_asin": ["a", "b"], "domain": ["D1", "D2"], "title": ["t1", "t2"]}
    base.update(extra)
    return pd.DataFrame(base)


def _categories(corpus):
    return sorted(corpus._conn.execute("SELECT item_id, category FROM item_categories"))


# ---------------------------------------------------------------- ids / namespacing
def test_same_original_id_in_two_domains_gives_two_distinct_items(world):
    rows = world.corpus.select("SELECT item_id, domain, original_item_id FROM items WHERE original_item_id='A1' ORDER BY item_id")[0]
    assert rows == [
        {"item_id": "Games::A1", "domain": "Games", "original_item_id": "A1"},
        {"item_id": "Toys::A1", "domain": "Toys", "original_item_id": "A1"},
    ]
    assert world.corpus.item_domains(["Games::A1", "Toys::A1"]) == {"Games::A1": "Games", "Toys::A1": "Toys"}


def test_there_is_no_plain_id_mode():
    import inspect

    assert "namespaced" not in inspect.signature(ItemCorpus.from_dataframe).parameters


def test_pipeline_output_form_original_item_id_is_accepted():
    # tag_domain() output: parent_asin already namespaced, original_item_id is the raw asin
    meta = pd.DataFrame({"parent_asin": ["D1::a"], "original_item_id": ["a"], "domain": ["D1"], "title": ["t"]})
    corpus = ItemCorpus.from_dataframe(meta)
    assert corpus.select("SELECT item_id, original_item_id FROM items")[0] == [{"item_id": "D1::a", "original_item_id": "a"}]


@pytest.mark.parametrize(
    "row",
    [
        {"parent_asin": "D1::a", "original_item_id": "ZZZ", "domain": "D1"},  # original does not match the id
        {"parent_asin": "D1::a", "original_item_id": "a", "domain": "D2"},  # id says D1, domain column says D2
        {"parent_asin": "a", "original_item_id": "a", "domain": "D1"},  # claims to be namespaced but is not
    ],
    ids=["wrong-original", "wrong-domain", "not-namespaced"],
)
def test_inconsistent_original_item_id_is_rejected(row):
    with pytest.raises(ValueError, match="original_item_id is inconsistent"):
        ItemCorpus.from_dataframe(pd.DataFrame([row]))


@pytest.mark.parametrize("bad", [None, "", "   ", 5])
def test_missing_or_blank_parent_asin_is_rejected(bad):
    with pytest.raises(ValueError, match="parent_asin"):
        ItemCorpus.from_dataframe(pd.DataFrame({"parent_asin": ["ok", bad], "domain": ["D", "D"]}))


# ---------------------------------------------------------------- domain precedence
def test_domain_argument_fills_missing_column():
    corpus = ItemCorpus.from_dataframe(pd.DataFrame({"parent_asin": ["a"], "title": ["t"]}), domain="D1")
    assert corpus.domains() == ["D1"]


def test_domain_argument_equal_to_column_is_silent():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        corpus = ItemCorpus.from_dataframe(pd.DataFrame({"parent_asin": ["a"], "domain": ["D1"]}), domain="D1")
    assert corpus.domains() == ["D1"]


def test_domain_argument_conflicting_with_column_is_rejected():
    with pytest.raises(ValueError, match="conflicts with the 'domain' column"):
        ItemCorpus.from_dataframe(_df(), domain="D1")  # row 'b' is in D2


@pytest.mark.parametrize("bad", [None, "", "  ", 3])
def test_missing_or_blank_domain_is_rejected(bad):
    with pytest.raises(ValueError, match="non-empty string domain"):
        ItemCorpus.from_dataframe(_df(domain=["D1", bad]))


# ---------------------------------------------------------------- categories
def test_string_category_is_one_category_not_characters():
    assert _categories(ItemCorpus.from_dataframe(_df(categories=["Games", ["x"]]))) == [("D1::a", "Games"), ("D2::b", "x")]


def test_category_cells_are_cleaned():
    corpus = ItemCorpus.from_dataframe(_df(categories=[[None, " Games ", "", float("nan"), "Games"], None]))
    assert _categories(corpus) == [("D1::a", "Games")]  # stripped, blank/None/NaN skipped, de-duplicated; missing -> none


def test_missing_categories_column_is_fine():
    assert _categories(ItemCorpus.from_dataframe(_df())) == []


@pytest.mark.parametrize("bad", [{"k": 1}, b"ab", 5, [["nested"]], [1, 2], [b"x"]], ids=repr)
def test_malformed_categories_raise_instead_of_corrupting_metadata(bad):
    with pytest.raises(ValueError, match="categories of item 'D1::a'"):
        ItemCorpus.from_dataframe(_df(categories=[bad, ["ok"]]))


def test_tiny_world_categories(world):
    assert _categories(world.corpus) == sorted(
        [("Games::A1", "Computers"), ("Games::A1", "Keyboards"), ("Games::B2", "Computers"), ("Games::C3", "Audio"),
         ("Toys::A1", "Puzzles"), ("Toys::A1", "Toys"), ("Toys::E5", "Toys")]
    )


# ---------------------------------------------------------------- numeric columns
def test_price_strings_are_parsed_and_junk_becomes_null():
    corpus = ItemCorpus.from_dataframe(_df(price=["$1,299.99", "from $5 to $9"]))
    assert [r["price"] for r in corpus.select("SELECT price FROM items ORDER BY item_id")[0]] == [1299.99, None]


def test_average_rating_is_always_numeric_even_with_junk():
    with pytest.warns(UserWarning, match="1 non-numeric average_rating"):
        corpus = ItemCorpus.from_dataframe(_df(average_rating=["4.5", "bad"]))
    types = corpus.select("SELECT typeof(average_rating) AS t FROM items ORDER BY item_id")[0]
    assert [r["t"] for r in types] == ["real", "null"]  # TEXT here would make `average_rating >= 4.4` true for 'bad'


def test_rating_number_policy_integral_fractional_missing_invalid():
    with pytest.warns(UserWarning, match="1 non-numeric rating_number"):
        corpus = ItemCorpus.from_dataframe(
            pd.DataFrame({"parent_asin": list("abcde"), "domain": "D", "rating_number": [10, 10.0, 10.7, None, "x"]})
        )
    values = [r["rating_number"] for r in corpus.select("SELECT rating_number FROM items ORDER BY item_id")[0]]
    assert values == [10, 10, 10.7, None, None]  # fractional kept as-is (NOT truncated to 10); missing/invalid -> NULL


# ---------------------------------------------------------------- build_corpus
def _write_meta(path, domain_rows):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for asin, title in domain_rows:
            f.write(json.dumps({"parent_asin": asin, "title": title, "store": "S", "categories": ["c"]}) + "\n")


def test_build_corpus_works_with_namespaced_mapping(tmp_path):
    _write_meta(tmp_path / "meta_D1.jsonl.gz", [("a", "t1"), ("b", "t2")])
    corpus, meta, coverage = build_corpus([("D1", str(tmp_path / "meta_D1.jsonl.gz"))], {"D1::a": 0, "D1::b": 1}, 0.5)
    assert coverage == 1.0 and len(meta) == 2 and corpus.domains() == ["D1"]


def test_build_corpus_rejects_plain_id_mapping(tmp_path):
    """The tools package only supports namespaced ids; a plain mapping has ~0% coverage and must fail loudly."""
    _write_meta(tmp_path / "meta_D1.jsonl.gz", [("a", "t1"), ("b", "t2")])
    with pytest.raises(ValueError):
        build_corpus([("D1", str(tmp_path / "meta_D1.jsonl.gz"))], {"a": 0, "b": 1}, 0.5)


# ---------------------------------------------------------------- read-only protection
@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM items",
        "INSERT INTO items(item_id, domain) VALUES ('x','y')",
        "UPDATE items SET title='x'",
        "DROP TABLE items",
        "SELECT 1; DELETE FROM items",
        "WITH x AS (SELECT 1) DELETE FROM items",
        "SELECT * FROM items; --",  # the ';' is not trailing, so this is two statements -> syntax error
        "PRAGMA query_only = OFF",
        "SELECT * FROM pragma_table_info('items')",
        "ATTACH DATABASE ':memory:' AS other",
        "CREATE TABLE t(x)",
        "not sql at all",
        "",
    ],
)
def test_writes_and_unsafe_statements_are_rejected_and_data_is_untouched(world, sql):
    before = world.corpus.select("SELECT COUNT(*) AS n FROM items")[0]
    result = QueryTool(world.corpus)(query=sql)
    assert not result.ok
    assert world.corpus.select("SELECT COUNT(*) AS n FROM items")[0] == before


def test_valid_select_and_cte_work(world):
    tool = QueryTool(world.corpus)
    assert tool(query="SELECT COUNT(*) AS n FROM items").data["items"] == [{"n": 6}]
    cte = "WITH g AS (SELECT item_id FROM items WHERE domain='Games') SELECT COUNT(*) AS n FROM g"
    assert tool(query=cte).data["items"] == [{"n": 4}]


def test_select_reports_truncation(world):
    rows, truncated = world.corpus.select("SELECT item_id FROM items ORDER BY item_id", max_rows=2)
    assert len(rows) == 2 and truncated
    rows, truncated = world.corpus.select("SELECT item_id FROM items", max_rows=6)
    assert len(rows) == 6 and not truncated


def test_select_non_select_raises_tool_input_error(world):
    with pytest.raises(ToolInputError):
        world.corpus.select("DELETE FROM items")
