import json
from pathlib import Path
import numpy as np
import pytest
from package.embeddings.ann_benchmark import exact_topk, benchmark_ann, synthetic_queries

def test_exact_topk_tie_order():
    vectors=np.array([[1.,0.],[1.,0.],[0.,1.]],dtype=np.float32)
    assert exact_topk(vectors,['b','a','c'],np.array([[1.,0.]],dtype=np.float32),2)==[['a','b']]


def test_filtering_short_pool_uses_exact_denominator(monkeypatch):
    from package.embeddings import ann_benchmark as bench
    ids=np.array(['a','b','c','d'])
    vectors=np.eye(4,dtype=np.float32)
    class Index:
        ntotal=4
        def add(self, vectors): pass
        def search(self, queries, k):
            return None,np.argsort(-(queries@vectors.T),axis=1)[:,:k]

    monkeypatch.setattr(bench,'load_benchmark_artifact',lambda _: (ids,vectors,{}))
    monkeypatch.setattr(bench,'_load_faiss',lambda: (object(),'mock'))
    monkeypatch.setattr(bench,'_build_index',lambda *_: Index())
    result=benchmark_ann(artifact=None,queries=vectors[:1],ks=[3],index_type='flat_ip',
                         eligible_mask=[False,True,True,True],seen_indices=[{0,1}],
                         warmup=0,repeats=2)
    assert result['recall']['3']['mean']==1
    assert result['latency_samples']==2
    assert result['incomplete_queries']==0

def test_synthetic_query_shape_and_normalization():
    q=synthetic_queries(np.zeros((4,3),dtype=np.float32),5,42)
    assert q.shape==(5,3); assert np.allclose(np.linalg.norm(q,axis=1),1.)

def test_paired_sweep_attributes_miss_and_builds_once(monkeypatch):
    from types import SimpleNamespace
    from package.embeddings import ann_benchmark as bench
    vectors=np.eye(3,dtype=np.float32)
    builds=[]
    class Index:
        ntotal=3
        hnsw=SimpleNamespace()
        def add(self, vectors): builds.append(len(vectors))
        def search(self, queries, k):
            positions=np.argsort(-(queries@vectors.T),axis=1)
            if self.hnsw.efSearch==512 and queries[0,0]:
                positions=positions[:,::-1]
            return None,positions[:,:k]
    monkeypatch.setattr(bench,'load_benchmark_artifact',lambda _: (np.array(list('abc')),vectors,{}))
    monkeypatch.setattr(bench,'_load_faiss',lambda: (object(),'mock'))
    monkeypatch.setattr(bench,'_build_index',lambda *_: Index())
    labels=[{'user_idx':7,'segment':'warm'},{'user_idx':9,'segment':'sparse'}]
    result=benchmark_ann(artifact=None,queries=vectors[:2],ks=[1],ef_sweep=[512,1024],
                         query_labels=labels,repeats=3,warmup=0)
    assert builds==[3]
    low,high=result['runs']['512'],result['runs']['1024']
    assert low['latency_samples']==high['latency_samples']==6
    assert low['per_query'][0]['user_idx']==7
    assert low['per_query'][0]['recall']['1']==0
    assert low['by_segment']['sparse']['recall']['1']==1
    assert high['by_segment']['warm']['recall']['1']==1

def test_benchmark_reports_unavailable_without_faiss(tmp_path,monkeypatch):
    artifact=tmp_path/'artifact'; artifact.mkdir()
    vectors=np.eye(3,dtype=np.float32); np.save(artifact/'vectors.npy',vectors); np.save(artifact/'item_ids.npy',np.array(['a','b','c']))
    import hashlib
    def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    manifest={'format_version':2,'status':'complete','kind':'full_catalog_embeddings','partial_catalog':False,'count':3,'catalog_count':3,'dimension':3,'files':{'vectors.npy':{'sha256':digest(artifact/'vectors.npy')},'item_ids.npy':{'sha256':digest(artifact/'item_ids.npy')}}}
    (artifact/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setitem(__import__('sys').modules,'faiss',None)
    result=benchmark_ann(artifact=artifact,queries=np.array([[1.,0.,0.]],dtype=np.float32),ks=[1])
    assert result['status']=='unavailable'
