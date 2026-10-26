"""Temporal policy is enforced at SQL access, not just in tool defaults."""
import sqlite3

import pandas as pd
import pytest

from package.tools import SQLTool, SemanticSearchTool
from package.tools.corpus import ItemCorpus
from package.tools.corpus.apply_metadata_policy import apply_metadata_policy


def make_corpus():
    return ItemCorpus.from_dataframe(pd.DataFrame({
        "parent_asin": ["a", "b"], "domain": ["D", "D"],
        "title": ["same keyboard", "same keyboard"], "price": [100., 5.],
        "average_rating": [1., 5.], "rating_number": [1, 100000],
    }))


def test_historical_masks_aggregates_and_price_in_all_tools():
    corpus = make_corpus()
    record = apply_metadata_policy(corpus, "historical_static_catalog", as_of_timestamp=10)
    assert record["historical_causal_claim"] is False
    rows, _ = corpus.select("SELECT * FROM items ORDER BY item_id")
    assert all(r[f] is None for r in rows for f in ("price", "average_rating", "rating_number"))
    assert [r["item_id"] for r in SQLTool(corpus).execute()["candidates"]] == ["D::a", "D::b"]
    assert [r["item_id"] for r in SemanticSearchTool(corpus).execute("keyboard")["candidates"]] == ["D::a", "D::b"]
    assert SQLTool(corpus).execute(filters={"min_rating_number": 2})["candidates"] == []
    assert SQLTool(corpus).execute(filters={"price_max": 50})["candidates"] == []
    assert apply_metadata_policy(corpus, "historical_static_catalog", as_of_timestamp=10) == record


@pytest.mark.parametrize("sql", [
    "SELECT price FROM main.items", "SELECT average_rating FROM main.items",
    "SELECT rating_number FROM main.items", "SELECT * FROM main.items",
    "SELECT i.rating_number FROM main.items AS i", "UPDATE items SET price=0",
    "DROP VIEW items", "PRAGMA query_only=OFF",
])
def test_no_sql_bypass(corpus, sql):
    apply_metadata_policy(corpus, "historical_static_catalog", as_of_timestamp=10)
    with pytest.raises(Exception):
        corpus.select(sql)


def test_snapshot_explicit_and_policy_cannot_be_changed():
    corpus = make_corpus()
    record = apply_metadata_policy(corpus, "snapshot", as_of_timestamp=10)
    assert record["snapshot_mutable_fields_used"]
    assert SQLTool(corpus).execute()["candidates"][0]["item_id"] == "D::b"
    with pytest.raises(ValueError, match="reload"):
        apply_metadata_policy(corpus, "historical_static_catalog", as_of_timestamp=10)


def test_temp_policy_preserves_main_data():
    corpus = make_corpus()
    apply_metadata_policy(corpus, "historical_static_catalog", as_of_timestamp=10)
    # Independent trusted check: underlying source is untouched by TEMP view.
    corpus._conn.set_authorizer(None)
    assert corpus._conn.execute("SELECT price FROM main.items WHERE item_id='D::a'").fetchone()[0] == 100


@pytest.mark.parametrize("cutoff", [None, 0, -1, True])
def test_cutoff_required(cutoff):
    with pytest.raises(ValueError, match="cutoff"):
        apply_metadata_policy(make_corpus(), "historical_static_catalog", as_of_timestamp=cutoff)


def test_deterministic_chain_uses_same_policy(cf_setup, corpus):
    from package.agents import build_tools
    from package.tools.recommenders import ItemKNNRecommender
    from package.tools.score import BaselineScorer
    interactions, user2id, item2id = cf_setup
    knn = ItemKNNRecommender(2).fit(interactions)
    apply_metadata_policy(corpus, "historical_static_catalog", as_of_timestamp=10)
    tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus)
    retrieved = tools.search.execute("game")
    ranked = tools.reco.execute(user_id="u3", candidates=[r["item_id"] for r in retrieved["candidates"]], top_k=2)
    assert ranked["ranked"]
    fetched = tools.query.execute(item_ids=[r["item_id"] for r in ranked["ranked"]])
    assert fetched["items"]
    assert all(r[f] is None for r in fetched["items"] for f in ("price", "average_rating", "rating_number"))
