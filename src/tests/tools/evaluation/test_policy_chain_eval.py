import json
from dataclasses import replace
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from package.tools.corpus import ItemCorpus
from package.tools.evaluation.policy_chain_compare import policy_chain_compare
from package.tools.evaluation.retrieval_loss_breakdown import retrieval_loss_breakdown
from package.tools.evaluation.ranking_run_store import RankingRunStore
from scripts.evaluation import policy_chain_eval as script
from tests.tools.evaluation.test_ranking_streaming import environment, launch


def record(segment="warm"):
    return dict(user_idx=1,segment=segment,candidate_sets={"union_all":["a","b","c"]},
                sources_after_seen_filter={"popularity":["b"],"item_cf":["a"],"semantic":["c"]},
                source_failures={"item_cf":None,"semantic":None},targets_unseen_in_fit=[1])


def baseline(pool): return dict(ids=list(pool),scores=list(range(len(pool),0,-1)))
def fetch(ids): return [{"item_id":i} for i in ids]


def test_cold_is_identical_and_order_is_seeded():
    a=policy_chain_compare(record("cold"),"union_all",baseline,fetch,seed=42)
    b=policy_chain_compare(record("cold"),"union_all",baseline,fetch,seed=42)
    assert [r["policy"] for r in a]==[r["policy"] for r in b]
    assert all(r["ranked_ids"]==["a","b","c"] and r["scores"]==[3,2,1] for r in a)
    assert all(not r["fallback"] and not r["policy_error"] for r in a)


def test_metadata_failure_is_visible_and_not_delivered():
    rows=policy_chain_compare(record(),"union_all",baseline,lambda ids:[],seed=42)
    assert all(r["metadata_error"] and not r["delivered_ids"] for r in rows)
    assert all(not r["fallback"] for r in rows)


def test_timeout_is_recorded_without_retry():
    calls=[]
    def timeout(ids):
        calls.append(ids)
        raise TimeoutError("fixture timeout")
    rows=policy_chain_compare(record(),"union_all",baseline,timeout,seed=42)
    assert len(calls)==3
    assert all("TimeoutError" in r["metadata_error"] and not r["fallback"] for r in rows)


def test_empty_pool_is_successful_empty_output():
    r=record(); r["candidate_sets"]["union_all"]=[]
    rows=policy_chain_compare(r,"union_all",baseline,fetch,seed=42)
    assert all(not x["policy_error"] and not x["metadata_error"] and not x["delivered_ids"] for x in rows)


def test_policy_failure_is_not_scored_as_success():
    rows=policy_chain_compare(record(),"union_all",lambda pool:dict(ids=["x"],scores=[1]),fetch,seed=42)
    b=next(r for r in rows if r["policy"]=="baseline")
    assert b["policy_error"] and b["ranked_ids"]==[] and b["delivered_ids"]==[]


def test_duplicate_input_aborts():
    r=record(); r["candidate_sets"]["union_all"]=["a","a"]
    with pytest.raises(ValueError,match="duplicate"):
        policy_chain_compare(r,"union_all",baseline,fetch,seed=42)


def test_retrieval_diagnostic_separates_losses_and_metadata():
    r=record(); r["targets_unseen_in_fit"]=[0,1,2,3]
    r["sources_raw"]={"popularity":["a","b","c"]}
    r["sources_after_seen_filter"]={"popularity":["a","b"]}
    r["candidate_sets"]={"union_rr":["a"],"union_all":["a","b"]}
    out=retrieval_loss_breakdown(r,{0:"a",1:"b",2:"c",3:"d"},{0,1,2},{"a","c","d"})["overall"]
    assert out["not_in_fit_catalog"]==1
    assert out["missing_metadata"]==1
    assert out["not_returned_by_any_source"]==1
    assert out["returned_raw_but_lost_in_source_filter_or_budget"]==1
    assert out["union_rr_merge_budget_loss"]==1


@pytest.mark.parametrize("mode",["frozen","fresh"])
@pytest.mark.parametrize("interrupted",[False,True])
def test_real_tools_smoke_and_completed_resume(environment,monkeypatch,mode,interrupted):
    base,paths,items=environment
    source=launch(monkeypatch,base,"ranking_reference")
    paths=replace(paths,experiments_dir=base/"policy_results")
    meta=pd.DataFrame({"parent_asin":[f"i{i}" for i in range(7)],"domain":["D"]*7,
                       "title":["Pok\u00e9mon keyboard"]*7})
    monkeypatch.setattr(script,"get_data_paths",lambda *a:paths)
    monkeypatch.setattr(script,"get_domains",lambda:["D"])
    monkeypatch.setattr(script,"build_corpus",lambda *a,**k:(ItemCorpus.from_dataframe(meta),meta,1.))
    argv=["policy_chain_eval","--source",str(source),"--item-knn",str(base/"ranking_reference"/"fit_item_knn.npz"),
          "--work-dir",str(base/("policy_"+mode)),"--per-segment","1","--bootstrap-samples","1000","--mode",mode]
    monkeypatch.setattr(sys,"argv",argv)
    if interrupted:
        append=RankingRunStore.append
        def crash(self,stream,batch):
            append(self,stream,batch)
            if stream=="union_all:baseline" and self.count(stream)==1:
                raise RuntimeError("fixture interruption after commit")
        with monkeypatch.context() as patch:
            patch.setattr(RankingRunStore,"append",crash)
            with pytest.raises(RuntimeError,match="fixture interruption"):
                script.main()
        monkeypatch.setattr(sys,"argv",argv+["--resume"])
    script.main()
    out=paths.experiments_dir/"policy_chain_eval"/"exp_001"
    result=json.loads((out/"metrics.json").read_text())
    assert result["mode"]==mode
    for seg,policies in result["comparison"]["union_all"].items():
        for p,r in policies.items():
            assert not any(r["errors"].values())
            assert bool(r["fresh_chain_service_latency"])==(mode=="fresh")
            if seg=="cold": assert r["cold_identical"]
    monkeypatch.setattr(sys,"argv",argv+["--resume"])
    script.main()
    assert len(list((paths.experiments_dir/"policy_chain_eval").glob("exp_*")))==1


def test_fresh_queries_do_not_depend_on_targets():
    r=record(); r["user_id"]="u1"
    config=dict(candidate_budget_per_source=2,retrieval={"seed_items":1,"query_items":1},
                protocol={"query_normalization":"ascii_fold"})
    calls=[]
    def semantic(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(ok=True,data={"candidates":[{"item_id":"c"}]},error=None)
    ctx=dict(recent={1:[0]},config=config,id2item={0:"a",1:"b",2:"c"},item2id={"a":0,"b":1,"c":2},
             popular=[1,2,0],cf=lambda **k:SimpleNamespace(ok=True,data={"candidates":[{"item_id":"b"}]},error=None),
             semantic=semantic,text=lambda ids:{"a":("history title","")})
    first=script._fresh(r,ctx)
    r["targets_unseen_in_fit"]=[999]
    second=script._fresh(r,ctx)
    assert first["candidate_sets"]==second["candidate_sets"]
    assert calls[0]==calls[1] and calls[0]["query"]=="history title"


def test_eligibility_is_shared_and_counted():
    rows=policy_chain_compare(record(),"union_all",baseline,fetch,seed=42,
                              eligible=lambda pool:[i for i in pool if i!="c"])
    assert all(set(r["ranked_ids"])=={"a","b"} and r["eligibility_removed"]==1 for r in rows)


def test_summary_failure_penalizes_delivered_quality(tmp_path):
    with RankingRunStore(tmp_path/"checkpoint",{"fixture":True}) as store:
        r=record()
        for merge in script.MERGES:
            r["candidate_sets"][merge]=["a","b","c"]
            rows=policy_chain_compare(r,merge,baseline,lambda ids:[],seed=42)
            for row in rows:
                row["retrieval_seconds"]=None
                store.append(f"{merge}:{row['policy']}",[(0,row)])
        out=script._summary(store,{"a":0,"b":1,"c":2},42,1000)
        b=out["union_all"]["warm"]["baseline"]
        assert b["metrics"]["recall@10"]==0
        assert b["pre_fetch_metrics"]["recall@10"]==1
        assert b["fresh_chain_service_latency"] is None
