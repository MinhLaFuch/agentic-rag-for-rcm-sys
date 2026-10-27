import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
import yaml

from scripts.evaluation.sparse_content_replay import compare, rrf, run
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash
from scripts.evaluation.analyze_ranking_bottlenecks import _metrics


def rows():
    cf=list('abcdefghijk'); bm=list('labc')
    common=dict(user_idx=0,targets=[11],seeds=['seed'],history_unique_items=1,candidate_budget=50,
        status='ok',error=None,metadata_missing_ids=[],excluded_seen=[],unscored_item_ids=[])
    a=dict(common,variant='cf_1',candidates=cf,ranked_ids=cf[:10],eligible_candidates=11)
    b=dict(common,variant='cf_bm25',candidates=cf+['l'],ranked_ids=cf[:10],eligible_candidates=12,
        source_events=[dict(tool=n,ok=True,data=dict(candidates=[dict(item_id=i) for i in ids]))
                       for n,ids in [('ItemCFTool',cf),('SemanticSearchTool',bm)]])
    return [a,b]


def test_rrf_fixed_formula_dedup_and_tie_breaking():
    assert rrf(['a','b'],['a'],['b'])==['a','b']
    assert rrf(['a','b','c'],['a','b'],['b','c'])==['b','a','c']
    with pytest.raises(ValueError,match='duplicate'): rrf(['a'],['a','a'],[])


def test_replay_metrics_segments_empty_gt_and_repeatability(tmp_path):
    records=rows(); empty=deepcopy(records)
    for r in empty: r.update(user_idx=1,targets=[])
    items={x:i for i,x in enumerate('abcdefghijkl')}
    first=compare(records+empty,items,42,1000,tmp_path/'a.jsonl')
    second=compare(records+empty,items,42,1000,tmp_path/'b.jsonl')
    assert first==second
    assert first['variants']['source_rrf60']['metrics']['hit_rate@10']==1
    assert first['variants']['cf_1']['metrics']['hit_rate@10']==0
    assert first['variants']['source_rrf60']['eligible_users']==1
    assert first['variants']['source_rrf60']['empty_ground_truth']==1
    assert first['history_segments']['1']['source_rrf60']['users']==2
    assert first['development_guardrails']['cf_1']['runtime_latency'] is None


@pytest.mark.parametrize('fault',['duplicate','missing','target','cf','pool','error'])
def test_reject_invalid_source(tmp_path,fault):
    r=rows()
    if fault=='duplicate': r.append(r[0])
    if fault=='missing': r=r[:1]
    if fault=='target': r[1]['targets']=[0]
    if fault=='cf': r[1]['source_events'][0]['data']['candidates']=[]
    if fault=='pool': r[1]['eligible_candidates']=1
    if fault=='error': r[1]['error']='failure'
    with pytest.raises(ValueError): compare(r,{x:i for i,x in enumerate('abcdefghijkl')},42,1000,tmp_path/'out')


def test_runner_publishes_hashes_and_reproduces_controls(tmp_path,monkeypatch):
    import scripts.evaluation.sparse_content_replay as module
    items={x:i for i,x in enumerate('abcdefghijkl')}; users={'user':0}
    source=tmp_path/'source';source.mkdir()
    data=dict(tag='toy',eval_on='validation',mapping_hash=mapping_hash(items),user_mapping_hash=mapping_hash(users))
    (source/'config.yaml').write_text(yaml.safe_dump(dict(run=dict(dataset=data),config=dict(identity=dict(retrieval_mode='cf_bm25')))))
    (source/'records.jsonl').write_text('\n'.join(map(json.dumps,rows())))
    (source/'requests.jsonl').write_text('{}')
    (source/'metrics.json').write_text(json.dumps(dict(variants={v:dict(metrics=_metrics(list('abcdefghij'),{11},items,10)) for v in ['cf_1','cf_bm25']})))
    hashes={n:file_hash(source/n) for n in ['config.yaml','records.jsonl','requests.jsonl','metrics.json']}
    (source/'artifact_hashes.json').write_text(json.dumps(hashes))
    monkeypatch.setattr(module,'get_data_paths',lambda tag:SimpleNamespace(mapped_dir=tmp_path,experiments_dir=tmp_path/'experiments'))
    monkeypatch.setattr(module,'load_mappings',lambda path:(users,items))
    run(SimpleNamespace(source=source,seed=42,bootstrap_samples=1000))
    output=tmp_path/'experiments'/'sparse_content_replay'/'exp_001'
    for n,h in json.loads((output/'artifact_hashes.json').read_text()).items():assert file_hash(output/n)==h
    assert not list(tmp_path.rglob('*.md'))
    assert hashes=={n:file_hash(source/n) for n in hashes}
    (source/'records.jsonl').write_text('corrupt')
    with pytest.raises(ValueError,match='hash'):run(SimpleNamespace(source=source,seed=42,bootstrap_samples=1000))
