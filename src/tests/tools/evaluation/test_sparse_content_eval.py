from dataclasses import replace
import json
import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

from package.tools import ItemCFTool,SemanticSearchTool,QueryTool
from package.tools.base import ToolResult
from package.tools.recommenders import ItemKNNRecommender
from package.tools.corpus import ItemCorpus
from scripts.evaluation import sparse_seed_eval as script
from tests.tools.evaluation.test_ranking_streaming import environment,launch


def test_source_quotas_dedup_and_fit_title_only(world):
    model=ItemKNNRecommender(2).fit(world.interactions)
    cf=ItemCFTool(model,world.item2id,corpus=world.corpus)
    search=SemanticSearchTool(world.corpus); query=QueryTool(world.corpus)
    provider=script._ContentRetriever(cf,search,query,["Games::A1"])
    result=provider(items=["Games::A1"],top_k=50)
    assert result.ok
    assert result.data["source_quotas"]=={"item_cf":25,"bm25":25}
    assert provider.events[0]["args"]["top_k"]==25
    assert provider.events[2]["args"]["limit"]==25
    assert provider.query_record["source_item_ids"]==["Games::A1"]
    assert provider.query_record["sent"]=="Quiet Mechanical Keyboard"
    ids=[r["item_id"] for r in result.data["candidates"]]
    assert len(ids)==len(set(ids))<=50
    control=cf(items=["Games::A1"],top_k=50)
    assert provider.events[0]["data"]["candidates"]==control.data["candidates"]


def test_bm25_failure_is_not_hidden_by_cf_fallback(world):
    cf=MagicMock(); cf.name="ItemCFTool"
    cf.return_value=ToolResult(ok=True,data={"candidates":[{"item_id":"Games::B2"}]})
    search=MagicMock(); search.name="SemanticSearchTool"; search.return_value=ToolResult(ok=False,error="fixture timeout")
    provider=script._ContentRetriever(cf,search,QueryTool(world.corpus),[])
    result=provider(items=["Games::A1"],top_k=50)
    assert not result.ok and result.error=="fixture timeout"
    assert len(provider.events)==3 and not provider.events[-1]["ok"]


def test_missing_history_metadata_is_visible(world):
    cf=MagicMock(); cf.name="ItemCFTool"; cf.return_value=ToolResult(ok=True,data={"candidates":[]})
    search=MagicMock()
    provider=script._ContentRetriever(cf,search,QueryTool(world.corpus),[])
    result=provider(items=["Games::unknown"],top_k=50)
    assert not result.ok
    search.assert_not_called()


@pytest.mark.parametrize('title',['c','the and','!!!',''])
def test_unsearchable_title_explicitly_preserves_baseline_ranker(world,title):
    model=ItemKNNRecommender(2).fit(world.interactions)
    cf=ItemCFTool(model,world.item2id,corpus=world.corpus)
    query=MagicMock();query.name='QueryTool'
    query.return_value=ToolResult(ok=True,data={'items':[{'item_id':'Games::A1','title':title}]})
    search=MagicMock();provider=script._ContentRetriever(cf,search,query,[])
    retrieved=provider(items=['Games::A1'],top_k=50)
    assert retrieved.ok and provider.fallback_reason=='no_searchable_title_tokens'
    assert retrieved.data['candidates']==cf(items=['Games::A1'],top_k=50).data['candidates']
    search.assert_not_called()
    ranker=MagicMock(); ranker.return_value=ToolResult(ok=True,data={'ranked':[{'item_id':'sentinel','score':.42}]})
    result=script._RRFModelTool(ranker,provider)(user_id='u',candidates=['a'],top_k=10)
    assert result is ranker.return_value
    ranker.assert_called_once_with(user_id='u',candidates=['a'],top_k=10)


@pytest.mark.parametrize('mode',['cf_bm25','cf_bm25_rrf','cf_bm25_history'])
def test_content_runner_confirms_baseline_and_saves_fixed_budget(environment,monkeypatch,mode):
    base,paths,items=environment
    source=launch(monkeypatch,base,"content_reference")
    paths=replace(paths,experiments_dir=base/"content_results")
    meta=pd.DataFrame({"parent_asin":[f"i{i}" for i in range(7)],"domain":["D"]*7,"title":["keyboard"]*7})
    monkeypatch.setattr(script,"get_data_paths",lambda *a:paths)
    monkeypatch.setattr(script,"get_domains",lambda:["D"])
    monkeypatch.setattr(script,"build_corpus",lambda *a,**k:(ItemCorpus.from_dataframe(meta),meta,1.))
    original=script.load_config
    monkeypatch.setattr(script,"load_config",lambda name:{"baselines":{"item_knn":{"k":2}}} if name=="eval/baselines" else original(name))
    common=["sparse_seed_eval","--source",str(source),"--item-knn",str(base/"content_reference"/"fit_item_knn.npz"),"--users","1","--bootstrap-samples","1000"]
    monkeypatch.setattr(sys,"argv",common+["--work-dir",str(base/"seed_control")]); script.main()
    reference=paths.experiments_dir/"sparse_seed_eval"/"exp_001"
    args=common+["--retrieval-mode",mode,"--baseline-from",str(reference),"--work-dir",str(base/"content_work")]
    monkeypatch.setattr(sys,"argv",args); script.main()
    output=paths.experiments_dir/"sparse_content_eval"/"exp_001"
    rows=[json.loads(line) for line in (output/"records.jsonl").read_text().splitlines()]
    control=rows[0];hybrid=next(r for r in rows if r['variant']==mode)
    assert control["variant"]=="cf_1" and hybrid["variant"]==mode
    assert control["seeds"]==hybrid["seeds"] and control["targets"]==hybrid["targets"]
    assert control["candidate_budget"]==hybrid["candidate_budget"]==50
    assert sum(hybrid["source_quotas"].values())==50
    assert len(hybrid["candidates"])<=50
    assert not list(output.glob("*.md"))
    metrics=json.loads((output/"metrics.json").read_text())
    assert set(metrics["variants"])==({'cf_1','cf_bm25_rrf','cf_bm25_history'} if mode=='cf_bm25_history' else {"cf_1",mode})
    assert metrics["variants"][mode]["content_sources"]["requests"]==1
    if mode in ('cf_bm25_rrf','cf_bm25_history'):
        from scripts.evaluation.sparse_content_replay import rrf
        pool=[i for i in hybrid['candidates'] if i not in hybrid['excluded_seen']+hybrid['unscored_item_ids']]
        assert hybrid['ranked_ids']==rrf(pool,hybrid['source_candidates']['item_cf'],hybrid['source_candidates']['bm25'])[:10]
        assert hybrid['count_equivalence']['equal']
        assert metrics['count_equivalence_checks']==1
        assert hybrid['events'][-1]['tool']=='QueryTool'
    if mode=='cf_bm25_history':
        assert metrics['retrieval_query_comparison']['variants']['cf_bm25_history']['users']==1
        assert set(hybrid['query_provenance']['source_item_ids'])<=set(items)
    monkeypatch.setattr(sys,"argv",args+["--resume"]); script.main()
    assert len(list(output.parent.glob("exp_*")))==1


@pytest.mark.parametrize('query',['keyboard','zzzznomatch'])
def test_no_count_preserves_candidates_scores_order_and_skips_count(world,monkeypatch,query):
    original=world.corpus.select; calls=[]
    def select(sql,*args,**kwargs):
        calls.append(sql)
        return original(sql,*args,**kwargs)
    monkeypatch.setattr(world.corpus,'select',select)
    counted=SemanticSearchTool(world.corpus)(query=query,limit=1)
    calls.clear()
    skipped=SemanticSearchTool(world.corpus,exact_count=False)(query=query,limit=1)
    assert counted.ok and skipped.ok
    assert skipped.data['total_matches'] is None
    assert all('COUNT(*)' not in sql for sql in calls)
    assert {k:v for k,v in counted.data.items() if k!='total_matches'}=={k:v for k,v in skipped.data.items() if k!='total_matches'}
