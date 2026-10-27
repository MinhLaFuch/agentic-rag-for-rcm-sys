from dataclasses import replace
import json
import sys

import pandas as pd
import pytest

from package.agents import Type1Agent
from package.agents.type1.recent_seed_items import recent_seed_items
from package.demo import DemoRequest,LiveBackend
from package.tools import ItemCFTool,RecoModelTool,QueryTool
from package.tools.score import BaselineScorer
from package.tools.recommenders import ItemKNNRecommender
from package.tools.corpus import ItemCorpus
from package.tools.evaluation.ranking_run_store import RankingRunStore
from scripts.evaluation import sparse_seed_eval as script
from tests.tools.evaluation.test_ranking_streaming import environment,launch


def test_recent_unique_seeds_match_last_row_ties_without_duplicates():
    history=pd.DataFrame({"item_idx":[0,1,0,2],"timestamp":[1,3,4,4]})
    assert recent_seed_items(history,{0:"a",1:"b",2:"c"},1)==["c"]
    assert recent_seed_items(history,{0:"a",1:"b",2:"c"},4)==["c","a","b"]
    with pytest.raises(ValueError): recent_seed_items(history,{0:"a"},0)


def test_actual_type1_and_live_backend_baseline_parity(corpus,cf_setup):
    fit,users,items=cf_setup
    fit=fit.assign(timestamp=list(range(len(fit))))
    model=ItemKNNRecommender(2).fit(fit)
    tools=(ItemCFTool(model,items,corpus=corpus),RecoModelTool(BaselineScorer(model),users,items,corpus=corpus),QueryTool(corpus))
    u=int(fit.user_idx.iloc[0]); user=next(k for k,v in users.items() if v==u)
    history=fit[fit.user_idx==u]; id2item={v:k for k,v in items.items()}
    row=script._run(tools,user,history,id2item,1,10)
    backend=LiveBackend(); backend._initialized=True; backend._fit_df=fit
    backend._user_id_to_internal_id=users; backend._internal_id_to_item_id=id2item
    backend._type1_agent=Type1Agent(*tools)
    shown=backend.respond(DemoRequest(user,"recommend",0,False,"type1"))
    assert shown.status==row["status"]
    assert [r.item_id for r in shown.items]==row["ranked_ids"]
    assert row["events"][0]["args"]["items"]==[id2item[int(history.iloc[-1].item_idx)]]
    assert row["events"][0]["args"]["top_k"]==50


def test_multiple_distinct_seeds_change_only_retrieval_input(corpus,cf_setup):
    fit,users,items=cf_setup
    fit=fit.assign(timestamp=list(range(len(fit))))
    user_idx=int(fit.groupby("user_idx").item_idx.nunique().idxmax())
    history=fit[fit.user_idx==user_idx]; unique=int(history.item_idx.nunique())
    assert unique>=2
    model=ItemKNNRecommender(2).fit(fit)
    tools=(ItemCFTool(model,items,corpus=corpus),RecoModelTool(BaselineScorer(model),users,items,corpus=corpus),QueryTool(corpus))
    name=next(k for k,v in users.items() if v==user_idx); inverse={v:k for k,v in items.items()}
    rows=[script._run(tools,name,history,inverse,n,10) for n in [1,2,4]]
    assert [r["actual_seed_count"] for r in rows]==[1,min(2,unique),min(4,unique)]
    assert all(r["events"][0]["args"]["top_k"]==50 for r in rows)
    assert all(len(r["seeds"])==len(set(r["seeds"])) for r in rows)


@pytest.mark.parametrize("interrupted",[False,True])
def test_runner_json_only_same_sample_budget_and_resume(environment,monkeypatch,interrupted):
    base,paths,items=environment
    source=launch(monkeypatch,base,"seed_reference")
    paths=replace(paths,experiments_dir=base/"seed_results")
    meta=pd.DataFrame({"parent_asin":[f"i{i}" for i in range(7)],"domain":["D"]*7,"title":["keyboard"]*7})
    monkeypatch.setattr(script,"get_data_paths",lambda *a:paths)
    monkeypatch.setattr(script,"get_domains",lambda:["D"])
    monkeypatch.setattr(script,"build_corpus",lambda *a,**k:(ItemCorpus.from_dataframe(meta),meta,1.))
    original_config=script.load_config
    monkeypatch.setattr(script,"load_config",lambda name: {"baselines":{"item_knn":{"k":2}}} if name=="eval/baselines" else original_config(name))
    argv=["sparse_seed_eval","--source",str(source),"--item-knn",str(base/"seed_reference"/"fit_item_knn.npz"),
          "--work-dir",str(base/"seed_work"),"--users","1","--bootstrap-samples","1000"]
    monkeypatch.setattr(sys,"argv",argv)
    if interrupted:
        append=RankingRunStore.append
        def crash(self,stream,batch):
            append(self,stream,batch)
            if stream=="seed_2" and self.count(stream)==1: raise RuntimeError("fixture interruption")
        with monkeypatch.context() as patch:
            patch.setattr(RankingRunStore,"append",crash)
            with pytest.raises(RuntimeError,match="fixture interruption"): script.main()
        monkeypatch.setattr(sys,"argv",argv+["--resume"])
    script.main()
    out=paths.experiments_dir/"sparse_seed_eval"/"exp_001"
    assert not list(out.glob("*.md"))
    rows=[json.loads(line) for line in (out/"records.jsonl").read_text().splitlines()]
    assert len(rows)==3 and len({r["user_idx"] for r in rows})==1
    assert {r["candidate_budget"] for r in rows}=={50}
    assert len({tuple(r["ranked_ids"]) for r in rows})==1  # only one history item
    assert len({tuple(r["targets"]) for r in rows})==1
    assert {r["actual_seed_count"] for r in rows}=={1}
    metrics=json.loads((out/"metrics.json").read_text())
    assert metrics["variants"]["2"]["paired_ndcg10"]["mean_delta"]==0
    monkeypatch.setattr(sys,"argv",argv+["--resume"]); script.main()
    assert len(list(out.parent.glob("exp_*")))==1
