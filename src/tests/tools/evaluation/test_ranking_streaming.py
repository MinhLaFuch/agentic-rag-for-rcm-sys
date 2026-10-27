"""Small end-to-end checkpoints exercise production tools, with no external LLM."""
from dataclasses import replace
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
import pytest

from package.config import get_data_paths
from package.tools.corpus import ItemCorpus
from package.tools.evaluation.ranking_run_store import RankingRunStore
from package.tools.evaluation.ranking_stream_summary import RankingStreamSummary
from scripts.evaluation import ranking_eval as script


@pytest.fixture
def environment(tmp_path, monkeypatch):
    paths = replace(get_data_paths("toy"), raw_dir=tmp_path/"raw", mapped_dir=tmp_path/"mapped",
                    splits_dir=tmp_path/"splits", corpus_dir=tmp_path/"corpus")
    paths.raw_dir.mkdir()
    paths.mapped_dir.mkdir()
    paths.splits_dir.mkdir()
    (paths.raw_dir/"meta_D.jsonl.gz").write_text("fixture metadata")
    user2id = {"u0":0,"u1":1,"u2":2}
    item2id = {f"D::i{i}":i for i in range(7)}
    for name,mapping in (("user2id",user2id),("item2id",item2id)):
        (paths.mapped_dir/(name+".json")).write_text(json.dumps(mapping))
    train = pd.DataFrame({"user_idx":[0]+[2]*6,"item_idx":[0]+list(range(6)),"timestamp":[1]*7})
    val = pd.DataFrame({"user_idx":[0,1,2],"item_idx":[2,3,6],"timestamp":[2]*3})
    test = val.assign(timestamp=3)
    for name,df in (("train",train),("validation",val),("test",test)):
        df.to_parquet(paths.split_path(name))
    meta = pd.DataFrame({"parent_asin":[f"i{i}" for i in range(7)],"domain":["D"]*7,
                         "title":["Pok\u00e9mon keyboard"]*7})
    monkeypatch.setattr(script,"get_data_paths",lambda *a:paths)
    monkeypatch.setattr(script,"get_domains",lambda:["D"])
    monkeypatch.setattr(script,"load_mappings",lambda *a:(user2id,item2id))
    monkeypatch.setattr(script,"build_corpus",lambda *a,**k:(ItemCorpus.from_dataframe(meta),meta,1.))
    return tmp_path,paths,item2id


def launch(monkeypatch, base, name, *, resume=False, frozen=None, weights="1e-6"):
    args = ["ranking_eval", "--tag","toy","--per-segment","2","--candidate-budget","3",
            "--ks","1,3","--neighbors","2","--popularity-weights",weights,
            "--query-normalization","ascii_fold","--no-prebuilt-corpus",
            "--work-dir",str(base/name),"--experiments-dir",str(base/(name+"_output")),
            "--batch-size","1","--progress-every","1"]
    if resume:
        args += ["--resume"]
    if frozen:
        args += ["--candidates-from",str(frozen)]
    monkeypatch.setattr(sys,"argv",args)
    script.main()
    return base/(name+"_output")/"exp_001"


@pytest.mark.parametrize("interrupt_stage", ["candidates", "scored:"])
def test_uninterrupted_and_resume_produce_identical_quality(environment,monkeypatch,interrupt_stage):
    base,paths,items = environment
    reference = launch(monkeypatch,base,"reference")
    original = RankingRunStore.append
    def interrupt(self,stream,batch):
        original(self,stream,batch)
        if stream.startswith(interrupt_stage) and self.count(stream)==1:
            raise RuntimeError("simulated power loss after commit")
    with monkeypatch.context() as patch:
        patch.setattr(RankingRunStore,"append",interrupt)
        with pytest.raises(RuntimeError,match="power loss"):
            launch(patch,base,"resumed")
    result = launch(monkeypatch,base,"resumed",resume=True)
    for name in ("candidate_lists.jsonl","scored.jsonl"):
        a=[json.loads(l) for l in (reference/name).read_text(encoding="utf8").splitlines()]
        b=[json.loads(l) for l in (result/name).read_text(encoding="utf8").splitlines()]
        for rows in (a,b):
            for row in rows:
                for field in ("source_latency_seconds","ranking_latency_seconds","fetch_latency_seconds"):
                    row.pop(field,None)
        assert a==b
    m=json.loads((result/"metrics.json").read_text())
    assert sum(v["semantic_errors"] for v in m["tool_health"].values())==0
    # The stream summary reproduces existing batch metric implementations.
    rows=[json.loads(l) for l in (result/"scored.jsonl").read_text().splitlines()]
    for merge in script.MERGES:
        for segment in script.SEGMENTS:
            selected=[r for r in rows if r["merge"]==merge and r["segment"]==segment and r["targets_unseen_in_fit"]]
            old=script._ranking_metrics([[items[i] for i in r["ranked_ids"]] for r in selected],
                                       [set(r["targets_unseen_in_fit"]) for r in selected],[1,3],len(items))
            assert old["metrics"]==m["ranking"][merge]["baseline"]["per_segment"][segment]["metrics"]
    # A finished checkpoint is idempotent and does not publish exp_002.
    launch(monkeypatch,base,"resumed",resume=True)
    assert not (result.parent/"exp_002").exists()


def test_frozen_candidates_and_weight_variants(environment,monkeypatch):
    base,paths,items = environment
    source = launch(monkeypatch,base,"source")
    def no_retrieval(*a,**k):
        raise AssertionError("frozen mode must not call SemanticSearch")
    monkeypatch.setattr(script.SemanticSearchTool,"execute",no_retrieval)
    result=launch(monkeypatch,base,"frozen",frozen=source,weights="0,1e-6")
    assert (source/"candidate_lists.jsonl").read_bytes()==(result/"candidate_lists.jsonl").read_bytes()
    m=json.loads((result/"metrics.json").read_text())
    assert set(m["ranking"]["union_rr"])=={"baseline","popularity_weight_0"}
    for merge in script.MERGES:
        for segment in script.SEGMENTS:
            a=json.loads((source/"metrics.json").read_text())["ranking"][merge]["baseline"]["per_segment"][segment]
            b=m["ranking"][merge]["baseline"]["per_segment"][segment]
            assert a["metrics"]==b["metrics"]


def test_resume_after_export_failure_skips_models(environment,monkeypatch):
    base,paths,items = environment
    export = RankingRunStore.export
    def fail(self,streams,destination):
        export(self,streams,destination)
        if Path(destination).name == "scored.jsonl":
            raise RuntimeError("export interrupted")
    with monkeypatch.context() as patch:
        patch.setattr(RankingRunStore,"export",fail)
        with pytest.raises(RuntimeError,match="export interrupted"):
            launch(patch,base,"export_resume")
    assert not (base/"export_resume_output"/"exp_001").exists()
    def no_models(*a,**k):
        raise AssertionError("completed scoring must not rebuild models on resume")
    monkeypatch.setattr(script,"_run_stages",no_models)
    result=launch(monkeypatch,base,"export_resume",resume=True)
    assert len((result/"scored.jsonl").read_text().splitlines())==6


def test_resume_after_publication_marker_failure(environment,monkeypatch):
    base,paths,items = environment
    put = RankingRunStore.put
    def fail(self,key,value):
        if key == "final_experiment":
            raise RuntimeError("marker interrupted")
        return put(self,key,value)
    with monkeypatch.context() as patch:
        patch.setattr(RankingRunStore,"put",fail)
        with pytest.raises(RuntimeError,match="marker interrupted"):
            launch(patch,base,"published")
    assert (base/"published_output"/"exp_001").exists()
    def no_finalize(*a,**k):
        raise AssertionError("already published experiment must be recovered, not republished")
    monkeypatch.setattr(script,"_finalize",no_finalize)
    launch(monkeypatch,base,"published",resume=True)
    assert not (base/"published_output"/"exp_002").exists()


def test_failed_baseline_confirmation_stops_tuning(environment,monkeypatch):
    base,paths,items = environment
    source=launch(monkeypatch,base,"bad_source")
    path=source/"metrics.json"
    metrics=json.loads(path.read_text())
    metrics["ranking"]["union_rr"]["baseline"]["per_segment"]["cold"]["metrics"]["1"]["ndcg@1"] += .1
    path.write_text(json.dumps(metrics))
    original=script.BaselineScorer
    called=[]
    def record(*a,**k):
        called.append(k["popularity_weight"])
        return original(*a,**k)
    monkeypatch.setattr(script,"BaselineScorer",record)
    with pytest.raises(ValueError,match="baseline confirmation failed"):
        launch(monkeypatch,base,"blocked_tuning",frozen=source,weights="0,1e-6")
    assert called==[1e-6]
    assert not (base/"blocked_tuning_output"/"exp_001").exists()
