import json
import sqlite3
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from package.tools.corpus import ItemCorpus
from package.tools.recommenders.mapping_hash import mapping_hash
from scripts.evaluation import build_semantic_embeddings as script


@pytest.fixture
def setup(tmp_path):
    mapping={'D::a':0,'D::b':1,'D::c':2,'D::d':3}
    mapped=tmp_path/'item2id.json';mapped.write_text(json.dumps(mapping))
    corpus=ItemCorpus.from_dataframe(pd.DataFrame({'parent_asin':['a','b','c','d'],'domain':['D']*4,'title':['keyboard','mouse','camera','lens']}))
    path=tmp_path/'corpus.sqlite';disk=sqlite3.connect(path);corpus._conn.backup(disk);disk.close()
    snapshot=tmp_path/'snapshot';snapshot.mkdir();(snapshot/'model.safetensors').write_bytes(b'fixture')
    lock=tmp_path/'encoder_lock.json'
    script.atomic(lock,dict(model_id=script.MODEL,revision='a'*40,status='ready',snapshot=str(snapshot),
        model_files={'model.safetensors':script.digest(snapshot/'model.safetensors')},environment=script.environment()))
    source=tmp_path/'source';source.mkdir()
    cfg={'run':{'dataset':{'eval_on':'validation','mapping_hash':mapping_hash(mapping)}}}
    (source/'config.yaml').write_text(yaml.safe_dump(cfg))
    for n in ['metrics.json','records.jsonl','requests.jsonl']:(source/n).write_text('{}')
    script.atomic(source/'artifact_hashes.json',{n:script.digest(source/n) for n in ['config.yaml','metrics.json','records.jsonl','requests.jsonl']})
    return SimpleNamespace(lock=lock,source=source,corpus=path,mapping=mapped,out=tmp_path/'vectors',
        batch_size=2,chunk_size=2,threads=1,limit_items=0,device='cpu',resume=False)


class Encoder:
    def __init__(self,fail=False):self.calls=0;self.fail=fail
    def encode(self,texts,**kwargs):
        self.calls+=1
        if self.fail and self.calls==2:raise RuntimeError('simulated interruption')
        vectors=np.zeros((len(texts),script.DIM),dtype=np.float32);vectors[:,0]=1
        return vectors


def test_full_build_resumes_and_preserves_source(setup):
    a=setup;before=script.digest(a.corpus);bad=Encoder(fail=True)
    with pytest.raises(RuntimeError,match='interruption'):script.build(a,lambda lock:bad)
    assert json.loads((a.out/'checkpoint.json').read_text())['completed']==2
    assert not (a.out/'manifest.json').exists()
    a.resume=True;encoder=Encoder();script.build(a,lambda lock:encoder)
    assert encoder.calls==1
    manifest=json.loads((a.out/'manifest.json').read_text())
    assert manifest['rows']==manifest['valid_rows']==4
    assert manifest['identity']['scope']=='full_mapping_catalog'
    assert manifest['quality_evaluated'] is False
    for n,h in manifest['artifact_hashes'].items():assert script.digest(a.out/n)==h
    assert np.allclose(np.linalg.norm(np.load(a.out/'vectors.npy'),axis=1),1)
    assert script.digest(a.corpus)==before
    script.build(a,lambda lock:pytest.fail('completed artifact must not re-encode'))
    assert not list(a.out.glob('*.md'))


def test_resume_rejects_committed_chunk_corruption(setup):
    a=setup
    with pytest.raises(RuntimeError):script.build(a,lambda lock:Encoder(fail=True))
    v=np.load(a.out/'vectors.npy',mmap_mode='r+');v[0,0]=.5;v.flush();del v
    a.resume=True
    with pytest.raises(ValueError,match='chunk checksum'):script.build(a,lambda lock:Encoder())


def test_protocol_change_and_existing_output_are_rejected(setup):
    a=setup;script.build(a,lambda lock:Encoder())
    with pytest.raises(ValueError,match='checkpoint exists'):script.build(a,lambda lock:Encoder())
    a.resume=True;a.batch_size=1
    with pytest.raises(ValueError,match='protocol mismatch'):script.build(a,lambda lock:Encoder())


def test_partial_catalog_is_explicit_and_mapping_hash_matches_runtime(setup):
    a=setup;a.limit_items=2
    assert script.mapping_identity(a.mapping)[1]==mapping_hash(json.loads(a.mapping.read_text()))
    script.build(a,lambda lock:Encoder())
    m=json.loads((a.out/'manifest.json').read_text())
    assert m['rows']==2 and m['identity']['scope']=='technical_subset_NOT_quality_catalog'


def test_bad_encoder_norms_do_not_publish(setup):
    class Zero:
        def encode(self,texts,**kwargs):return np.zeros((len(texts),script.DIM),dtype=np.float32)
    with pytest.raises(ValueError,match='invalid encoder output'):script.build(setup,lambda lock:Zero())
    assert not (setup.out/'manifest.json').exists()


def test_lock_and_source_tampering_rejected(setup):
    (setup.source/'metrics.json').write_text('changed')
    with pytest.raises(ValueError,match='source artifact'):script.build(setup,lambda lock:Encoder())
    lock=json.loads(setup.lock.read_text());lock['revision']='main';script.atomic(setup.lock,lock)
    with pytest.raises(ValueError,match='immutable'):script.verify_lock(setup.lock)


def test_pin_retry_does_not_resolve_main_again(tmp_path,monkeypatch):
    snapshot=tmp_path/'snapshot';snapshot.mkdir();(snapshot/'1_Pooling').mkdir()
    for n in ('modules.json','model.safetensors','config.json','1_Pooling/config.json'):(snapshot/n).write_text('{}')
    calls={'resolve':0,'download':0}
    class API:
        def model_info(self,model):calls['resolve']+=1;return SimpleNamespace(sha='b'*40)
    def download(**kwargs):
        calls['download']+=1;assert kwargs['revision']=='b'*40
        if calls['download']==1:raise OSError('interrupted download')
        return str(snapshot)
    monkeypatch.setitem(sys.modules,'huggingface_hub',SimpleNamespace(HfApi=API,snapshot_download=download))
    a=SimpleNamespace(lock=tmp_path/'encoder_lock.json',cache_dir=tmp_path/'cache')
    with pytest.raises(OSError):script.pin(a)
    assert json.loads(a.lock.read_text())['revision']=='b'*40
    script.pin(a);script.pin(a)
    assert calls=={'resolve':1,'download':2}
    assert (tmp_path/'requirements.lock.txt').exists()
