"""Temporal policy is enforced at SQL access, not just in tool defaults."""
import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest
from scipy.sparse import csr_matrix

from package.tools import ItemCFTool, QueryTool, SQLTool, SemanticSearchTool
from package.tools.corpus import ItemCorpus
from package.tools.corpus.apply_metadata_policy import apply_metadata_policy
from package.memory import MemoryTool


def make_corpus():
    return ItemCorpus.from_dataframe(pd.DataFrame({
        "parent_asin": ["a", "b"], "domain": ["D", "D"],
        "title": ["visible keyboard", "future launchtoken keyboard"],
        "first_seen_ts": [5, 15], "categories": [["Past"], ["FutureOnly"]],
        "price": [100., 5.],
        "average_rating": [1., 5.], "rating_number": [1, 100000],
    }))


def test_historical_masks_aggregates_and_price_in_all_tools():
    corpus = make_corpus()
    record = apply_metadata_policy(corpus, "historical_static_catalog", as_of_timestamp=10)
    assert record["historical_causal_claim"] is False
    assert record["first_seen_filter"] is True
    rows, _ = corpus.select("SELECT * FROM items ORDER BY item_id")
    assert all(r[f] is None for r in rows for f in ("price", "average_rating", "rating_number"))
    assert [r["item_id"] for r in SQLTool(corpus).execute()["candidates"]] == ["D::a"]
    assert [r["item_id"] for r in SemanticSearchTool(corpus).execute("keyboard")["candidates"]] == ["D::a"]
    hidden_search = SemanticSearchTool(corpus).execute("launchtoken")
    assert hidden_search["candidates"] == [] and hidden_search["total_matches"] == 0
    query = QueryTool(corpus)
    assert query(item_ids=["D::b"]).data["missing_item_ids"] == ["D::b"]
    assert corpus.categories() == ["Past"]
    assert not corpus.category_exists("FutureOnly")
    assert corpus.item_domains(["D::a", "D::b"]) == {"D::a": "D"}
    assert corpus.select("SELECT rowid FROM items_fts WHERE items_fts MATCH 'launchtoken'")[0] == []
    with pytest.raises(Exception):
        corpus.select("SELECT item_id FROM main.items")
    with pytest.raises(Exception):
        corpus.select("SELECT rowid FROM main.items_fts WHERE main.items_fts MATCH 'launchtoken'")
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
    assert SQLTool(corpus).execute()["candidates"][0]["item_id"] == "D::a"
    with pytest.raises(ValueError, match="reload"):
        apply_metadata_policy(corpus, "historical_static_catalog", as_of_timestamp=10)


def test_first_seen_filter_covers_itemcf_and_memory():
    corpus = make_corpus()
    apply_metadata_policy(corpus, "snapshot", as_of_timestamp=10)
    model = SimpleNamespace(similarity=csr_matrix([[0.0, 1.0], [0.0, 0.0]]))
    cf = ItemCFTool(model, {"D::a": 0, "D::b": 1}, corpus=corpus)
    result = cf.execute(items=["D::a"], top_k=5)
    assert [r["item_id"] for r in result["candidates"]] == []

    interactions = pd.DataFrame({"user_idx": [0], "item_idx": [1], "timestamp": [8]})
    memory = MemoryTool(interactions, {"u": 0}, {"D::a": 0, "D::b": 1}, corpus, as_of_timestamp=10)
    snapshot = memory(user_id="u")
    assert snapshot.data["recent_items"] == []
    assert snapshot.data["top_categories"] == []
    assert snapshot.data["known"] is False


def test_memory_uses_catalog_cutoff_for_timestamped_history():
    corpus = make_corpus()
    apply_metadata_policy(corpus, "snapshot", as_of_timestamp=10)
    interactions = pd.DataFrame({"user_idx": [0], "item_idx": [0], "timestamp": [11]})
    memory = MemoryTool(interactions, {"u": 0}, {"D::a": 0}, corpus)
    assert memory(user_id="u").data["known"] is False


def test_memory_requires_timestamp_when_temporal_policy_is_active():
    corpus = make_corpus()
    apply_metadata_policy(corpus, "snapshot", as_of_timestamp=10)
    interactions = pd.DataFrame({"user_idx": [0], "item_idx": [0]})
    memory = MemoryTool(interactions, {"u": 0}, {"D::a": 0}, corpus)
    with pytest.raises(ValueError, match="timestamped interactions"):
        memory(user_id="u")


def test_temporal_policy_requires_first_seen_and_cannot_change_cutoff():
    no_timestamp = ItemCorpus.from_dataframe(pd.DataFrame({"parent_asin": ["x"], "domain": ["D"]}))
    with pytest.raises(ValueError, match="first_seen_ts"):
        apply_metadata_policy(no_timestamp, "snapshot", as_of_timestamp=10)
    corpus = make_corpus()
    apply_metadata_policy(corpus, "snapshot", as_of_timestamp=10)
    with pytest.raises(ValueError, match="reload"):
        apply_metadata_policy(corpus, "snapshot", as_of_timestamp=11)


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
