import sqlite3
import json
import sys
from dataclasses import replace

import pandas as pd

import pytest

from package.evaluation.recommender.analysis.outside_core_content_retriever import OutsideCoreContentRetriever


@pytest.fixture
def corpus():
    conn=sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE items(item_id TEXT PRIMARY KEY, first_seen_ts INTEGER, title TEXT, store TEXT, main_category TEXT)")
    conn.executemany("INSERT INTO items VALUES (?,?,?,?,?)", [
        ("seed",1,"quiet keyboard","A","Electronics"),
        ("core",1,"quiet keyboard","A","Electronics"),
        ("outside",1,"quiet keyboard","A","Electronics"),
        ("seen",1,"quiet keyboard","A","Electronics"),
        ("future",9,"quiet keyboard quiet keyboard","A","Electronics"),
        ("unknown",None,"quiet keyboard","A","Electronics")])
    yield conn
    conn.close()


def test_content_catalog_and_queries_are_temporal_and_exclude_core_and_full_history(corpus):
    probe=OutsideCoreContentRetriever(corpus,{"seed","core"},2)
    assert probe.visible_items==2
    row=probe.retrieve(["seed"],limit=1,excluded_ids=["seen"])
    assert row["status"]=="ok"
    assert row["candidates"]==["outside"]
    assert "keyboard" in row["query"]
    assert corpus.execute("SELECT COUNT(*) FROM items").fetchone()[0]==6
    plan=corpus.execute("EXPLAIN QUERY PLAN SELECT item_id,-rank FROM probe_fts WHERE probe_fts MATCH ? ORDER BY rank LIMIT 10",('keyboard',)).fetchall()
    assert not any("TEMP B-TREE" in str(row) for row in plan)


def test_cold_or_future_history_has_no_query(corpus):
    probe=OutsideCoreContentRetriever(corpus,{"seed","core"},2)
    assert probe.retrieve([])["status"]=="no_query"
    assert probe.retrieve(["future"])["candidates"]==[]


def test_timeout_or_sql_failure_is_explicit(corpus):
    probe=OutsideCoreContentRetriever(corpus,{"seed"},2)
    corpus.execute("DROP TABLE probe_fts")
    row=probe.retrieve(["seed"])
    assert row["status"]=="error"
    assert row["error"]
    assert row["candidates"]==[]


def test_probe_cli_writes_real_records_and_preserves_cold_denominators(tmp_path,monkeypatch):
    from scripts.evaluation import outside_core_content_probe as script
    from package.config import get_data_paths
    from package.recommenders.shared import file_hash
    from package.recommenders.shared import mapping_hash
    paths=replace(get_data_paths("toy"),mapped_dir=tmp_path/"mapped",splits_dir=tmp_path/"splits",
                  corpus_dir=tmp_path/"corpus",experiments_dir=tmp_path/"results")
    (paths.mapped_dir/"fit_core").mkdir(parents=True)
    paths.splits_dir.mkdir()
    paths.corpus_dir.mkdir()
    mapping={"D::seed":0,"D::outside":1,"D::future":2}
    (paths.mapped_dir/"item2id.json").write_text(json.dumps(mapping))
    (paths.mapped_dir/"fit_core"/"item2id.json").write_text(json.dumps({"D::seed":0}))
    (paths.splits_dir/"stage_3.manifest.json").write_text(json.dumps({
        "flags":{"data_protocol":"temporal_train_core"},"counts":{"num_users":3}}))
    pd.DataFrame({"user_idx":[0,1],"item_idx":[0,1],"timestamp":[1,1]}).to_parquet(paths.split_path("train"))
    pd.DataFrame({"user_idx":[0,1,2],"item_idx":[1,2,2],"timestamp":[2,2,2]}).to_parquet(paths.split_path("validation"))
    conn=sqlite3.connect(paths.corpus_path)
    conn.execute("CREATE TABLE items(item_id TEXT PRIMARY KEY, first_seen_ts INTEGER, title TEXT, store TEXT, main_category TEXT)")
    conn.executemany("INSERT INTO items VALUES (?,?,?,?,?)",[(key,3 if key.endswith("future") else 1,"quiet keyboard","A","Electronics") for key in mapping])
    conn.commit()
    conn.close()
    paths.corpus_path.with_suffix(".meta.json").write_text(json.dumps({
        "artifact_sha256":file_hash(paths.corpus_path),"mapping_hash":mapping_hash(mapping)}))
    monkeypatch.setattr(script,"get_data_paths",lambda *a,**k:paths)
    monkeypatch.setattr(sys,"argv",["probe","--per-segment","10"])
    script.main()
    directory=paths.experiments_dir/"outside_core_content"/"exp_001"
    records=[json.loads(line) for line in (directory/"records.jsonl").read_text().splitlines()]
    assert len(records)==3
    cold=next(r for r in records if r["segment"]=="cold")
    assert cold["content"]["status"]=="no_query"
    assert cold["metrics"]["outside_core_bm25"]["outside_core_recall@20"]==0
    known=next(r for r in records if r["user_idx"]==0)
    assert known["metrics"]["outside_core_bm25"]["outside_core_recall@20"]==1
    assert all("D::future" not in r["content"]["candidates"] for r in records)
    assert (directory/"summary"/"metrics.json").is_file()
