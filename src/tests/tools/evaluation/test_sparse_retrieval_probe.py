import json
import sqlite3
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp
import yaml

from package.tools.evaluation.classify_cf_link import classify_cf_link
from package.tools.evaluation.history_title_query import history_title_query
from package.tools.retrieval.tokenize_search_query import tokenize_search_query
from package.tools.recommenders.mapping_hash import mapping_hash
from package.tools.recommenders.file_hash import file_hash
from package.tools.corpus import ItemCorpus
from package.tools import SemanticSearchTool
from scripts.evaluation import sparse_retrieval_probe as script


@pytest.mark.parametrize('args,reason',[
    ((10,0,0,False,.1),'no_train_cooccurrence'),
    ((10,10,1,False,.2),'truncated_below_cutoff'),
    ((10,10,1,False,.1),'truncated_at_tied_cutoff'),
    ((10,10,1,True,.1),'in_cache'),
    ((10,10,5,False,.1),'above_cutoff_missing_requires_investigation')])
def test_cf_link_classes(args,reason):
    assert classify_cf_link(*args)['reason']==reason
    with pytest.raises(ValueError):classify_cf_link(1,1,2,False,.1)


def test_balanced_history_query_single_title_parity_and_runtime_cap():
    assert history_title_query(['Keyboard & Mouse'])=='Keyboard & Mouse'
    assert history_title_query(['keyboard mouse','camera lens'])=='keyboard camera mouse lens'
    query=history_title_query([' '.join(f'key{i}' for i in range(100)),'camera lens'])
    tokens=tokenize_search_query(query)
    assert tokens[1]=='camera' and tokens[3]=='lens'
    assert len(tokens)==len(tokenize_search_query(' '.join(f'key{i}' for i in range(100))))
    assert history_title_query(['c','the and'])==''


def test_probe_reproduces_saved_fts_and_checks_train_links(tmp_path,monkeypatch):
    items={'D::seed':0,'D::target':1,'D::other':2};users={'u':0,'v':1}
    train=tmp_path/'train.parquet'
    pd.DataFrame({'user_idx':[0,0,0,1],'item_idx':[0,1,1,0]}).to_parquet(train)
    model=tmp_path/'knn.npz';sp.save_npz(model,sp.csr_matrix(([.9],([0],[2])),shape=(3,3),dtype=np.float32))
    meta=pd.DataFrame({'parent_asin':['seed','target','other'],'domain':['D']*3,'title':['keyboard','mouse','keyboard']})
    corpus=ItemCorpus.from_dataframe(meta);path=tmp_path/'corpus.sqlite'
    disk=sqlite3.connect(path);corpus._conn.backup(disk);disk.close()
    result=SemanticSearchTool(corpus)(query='keyboard',filters={'exclude_item_ids':['D::seed']},limit=25)
    assert result.ok
    source=tmp_path/'source';source.mkdir()
    d=dict(tag='toy',eval_on='validation',mapping_hash=mapping_hash(items),user_mapping_hash=mapping_hash(users),split_files={'train':{'sha256':file_hash(train)}})
    cfg={'run':{'dataset':d},'config':{'identity':{'source':[{'path':str(model.resolve()),'sha256':file_hash(model)}]}}}
    (source/'config.yaml').write_text(yaml.safe_dump(cfg))
    (source/'metrics.json').write_text('{}');(source/'requests.jsonl').write_text('{}')
    r=dict(user_idx=0,variant='cf_bm25_rrf',status='ok',targets=[1],candidates=['D::other'],seeds=['D::seed'],history_unique_items=1,
        query_provenance={'sent':'keyboard'},source_events=[{'tool':'SemanticSearchTool','args':{'filters':{'exclude_item_ids':['D::seed']}},'data':result.data}])
    (source/'records.jsonl').write_text(json.dumps(r))
    hashes={n:file_hash(source/n) for n in ('config.yaml','metrics.json','requests.jsonl','records.jsonl')}
    (source/'artifact_hashes.json').write_text(json.dumps(hashes))
    monkeypatch.setattr(script,'get_data_paths',lambda tag:SimpleNamespace(mapped_dir=tmp_path,split_path=lambda s:train))
    monkeypatch.setattr(script,'load_mappings',lambda path:(users,items))
    metrics,_,_,_=script.probe(source,path,model,1,42)
    assert metrics['counts']=={'cf:truncated_below_cutoff':1,'bm25:no_lexical_match':1}
    assert metrics['details'][0]['cooccurrence_users']==1
    assert metrics['details'][0]['train_target_users']==1 # duplicate events excluded
    assert hashes=={n:file_hash(source/n) for n in hashes}
