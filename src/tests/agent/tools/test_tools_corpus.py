import pandas as pd
import pytest

from package.tools import ItemCorpus, QueryTool
from tests.tools_helpers import EL_A, VG_A, VG_B, VG_C


def test_corpus_namespaces_ids_so_equal_asins_do_not_collide(corpus):
    ids = {r["item_id"] for r in QueryTool(corpus)(query="SELECT item_id FROM items").data["items"]}
    assert {VG_A, EL_A} <= ids


def test_corpus_parses_price_strings_and_keeps_missing_as_null(corpus):
    rows = QueryTool(corpus)(query="SELECT item_id, price FROM items WHERE domain='Video_Games'").data["items"]
    prices = {r["item_id"]: r["price"] for r in rows}
    assert prices == {VG_A: 19.99, VG_B: None, VG_C: 5.5}


def test_corpus_rejects_duplicate_item_ids():
    meta = pd.DataFrame({"parent_asin": ["a", "a"], "title": ["x", "y"]})
    with pytest.raises(ValueError, match="duplicate"):
        ItemCorpus.from_dataframe(meta, domain="Video_Games")


def test_corpus_requires_a_domain():
    with pytest.raises(ValueError, match="domain"):
        ItemCorpus.from_dataframe(pd.DataFrame({"parent_asin": ["a"]}))
