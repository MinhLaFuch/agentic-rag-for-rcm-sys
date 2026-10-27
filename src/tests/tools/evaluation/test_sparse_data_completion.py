import json
import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash
from scripts.evaluation import sparse_data_diagnostic as data
from scripts.evaluation.sparse_guard_replay import compare,guarded_order
from scripts.evaluation.sparse_content_replay import rrf


def test_data_diagnosis_uses_unique_train_pairs_and_preserves_cold_targets(tmp_path,monkeypatch):
    items={'D::history':0,'D::target':1,'X::cold':2};users={'user':0}
    train=tmp_path/'train.parquet'
    pd.DataFrame({'user_idx':[0,0,0],'item_idx':[0,1,1]}).to_parquet(train)
    corpus=tmp_path/'corpus.sqlite';conn=sqlite3.connect(corpus)
    conn.execute('CREATE TABLE items(item_id TEXT,title TEXT)')
    conn.executemany('INSERT INTO items VALUES (?,?)',[('D::history','keyboard'),('D::target','game')]);conn.commit();conn.close()
    source=tmp_path/'source';source.mkdir()
    d=dict(tag='toy',eval_on='validation',mapping_hash=mapping_hash(items),user_mapping_hash=mapping_hash(users),
        split_files={'train':{'sha256':file_hash(train)}})
    (source/'config.yaml').write_text(yaml.safe_dump({'run':{'dataset':d},'config':{'sampled_user_ids':[0]}}))
    (source/'metrics.json').write_text('{}')
    req=dict(user_idx=0,targets=[1,2],history=[{'item_idx':0}])
    (source/'requests.jsonl').write_text(json.dumps(req)+'\n')
    base=dict(user_idx=0,variant='cf_1',targets=[1,2],ranked_ids=[])
    hybrid=dict(user_idx=0,variant='cf_bm25_rrf',targets=[1,2],ranked_ids=[],candidates=['D::target'],
        history_unique_items=1,seeds=['D::history'],query_provenance={'raw':'keyboard'})
    (source/'records.jsonl').write_text('\n'.join(map(json.dumps,[base,hybrid])))
    hashes={n:file_hash(source/n) for n in ('config.yaml','metrics.json','requests.jsonl','records.jsonl')}
    (source/'artifact_hashes.json').write_text(json.dumps(hashes))
    monkeypatch.setattr(data,'get_data_paths',lambda tag:SimpleNamespace(mapped_dir=tmp_path,split_path=lambda s:train))
    monkeypatch.setattr(data,'load_mappings',lambda path:(users,items))
    result,_,_,_=data.diagnose(source,corpus)
    c=result['counts']['overall']
    assert c['target_pairs']==2 and c['train_support_1_4']==1 and c['train_support_0']==1
    assert c['cross_history_domain']==1 and c['missing_metadata_snapshot']==1
    assert c['retrieved']==1 and c['not_retrieved']==1
    assert result['seed_metadata']['seed_title_matches_diagnostic_corpus']==1
    assert {n:file_hash(source/n) for n in hashes}==hashes
    (source/'metrics.json').write_text('changed')
    with pytest.raises(ValueError,match='hash mismatch'):data.diagnose(source,corpus)


def test_guard_retains_prefix_without_pool_additions_and_is_gt_independent():
    pool=list('abcdefghijklmno');fused=list(reversed(pool));baseline=list('abcdefghij')
    out=guarded_order(pool,baseline,fused)
    assert out[:5]==baseline[:5] and set(out)==set(pool) and len(out)==len(pool)
    assert guarded_order(['x'],['outside'],['x'])==['x']
    with pytest.raises(ValueError):guarded_order(['x','x'],[],['x'])


def test_guard_replay_keeps_errors_empty_gt_and_pairing(tmp_path):
    cf=[f'c{i}' for i in range(12)];bm=[f'b{i}' for i in range(12)];pool=cf+bm;items={i:n for n,i in enumerate(pool)}
    rows=[]
    for u,gt,status in [(0,[0],'ok'),(1,[],'ok'),(2,[1],'tool_error')]:
        common=dict(user_idx=u,targets=gt,seeds=['seed'],candidate_budget=50,history_unique_items=2)
        rows.append(dict(common,variant='cf_1',ranked_ids=cf[:10]))
        rows.append(dict(common,variant='cf_bm25_rrf',status=status,ranked_ids=rrf(pool,cf,bm)[:10] if status=='ok' else [],
            candidates=pool if status=='ok' else [],excluded_seen=[],unscored_item_ids=[],source_candidates={'item_cf':cf,'bm25':bm}))
    result=compare(rows,items,{1},42,1000,tmp_path/'out.jsonl')
    s=result['overall']['variants']['baseline_top5_guard']
    assert s['users']==3 and s['eligible_users']==2
    assert s['metrics']['hit_rate@10']==.5  # source tool error retained as a miss
    emitted=[json.loads(l) for l in (tmp_path/'out.jsonl').read_text().splitlines()]
    assert next(r for r in emitted if r['user_idx']==2 and r['policy']=='baseline_top5_guard')['ranked_ids_at10']==[]
    assert result['remaining_development']['variants']['cf_1']['users']==2
