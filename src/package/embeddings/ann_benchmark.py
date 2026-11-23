"""Optional exact-vs-ANN dense retrieval benchmark helpers."""
from __future__ import annotations
import hashlib, importlib.metadata, importlib.util, platform, subprocess, sys, time
from pathlib import Path
from typing import Sequence
import numpy as np
from .load_vector_artifact import load_vector_artifact

def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def _percentiles(values):
    if not values: return {"p50_seconds": None, "p95_seconds": None, "p99_seconds": None}
    return {f"p{p}_seconds": float(np.percentile(values, p)) for p in (50, 95, 99)}

def _git_provenance():
    try:
        sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
        dirty=bool(subprocess.check_output(["git","status","--porcelain"],text=True).strip())
    except (OSError, subprocess.CalledProcessError): sha,dirty=None,None
    return {"sha":sha,"dirty":dirty}

def load_benchmark_artifact(path):
    path = Path(path)
    ids, vectors, manifest = load_vector_artifact(path)
    manifest = dict(manifest)
    manifest['manifest_sha256'] = _sha256(path / 'manifest.json')
    manifest['vector_sha256'] = _sha256(path / 'vectors.npy')
    manifest['item_id_sha256'] = _sha256(path / 'item_ids.npy')
    return ids, vectors, manifest

def exact_topk(vectors,item_ids,queries,k,*,eligible_mask=None,seen_indices=None):
    if k<=0: raise ValueError("k must be positive")
    q=np.asarray(queries,dtype=np.float32); ids=np.asarray(item_ids,dtype=str)
    if q.ndim!=2 or q.shape[1]!=vectors.shape[1]: raise ValueError("query shape/dimension mismatch")
    norms=np.linalg.norm(q,axis=1,keepdims=True)
    if np.any(norms<=1e-9) or not np.isfinite(q).all(): raise ValueError("queries must be finite and non-zero")
    q=q/norms; valid=np.ones(len(ids),dtype=bool) if eligible_mask is None else np.asarray(eligible_mask,dtype=bool)
    if valid.shape!=(len(ids),): raise ValueError('eligible mask shape mismatch')
    seen_indices=seen_indices or [set() for _ in range(len(q))]
    if len(seen_indices)!=len(q): raise ValueError('seen exclusions length mismatch')
    result=[]
    for row,vector in enumerate(q):
        mask=valid.copy()
        if seen_indices[row]:
            excluded=np.asarray(sorted(seen_indices[row]),dtype=np.int64)
            if np.any(excluded<0) or np.any(excluded>=len(ids)): raise ValueError('seen index out of bounds')
            mask[excluded] = False
        best=np.empty(0,dtype=np.int64)
        best_scores=np.empty(0,dtype=np.float32)
        for start in range(0,len(ids),32768):
            block=vectors[start:start+32768]
            local=np.flatnonzero(mask[start:start+len(block)])
            scores=np.concatenate((best_scores,(block@vector)[local]))
            positions=np.concatenate((best,start+local))
            order=np.lexsort((ids[positions],-scores))[:k]
            best,best_scores=positions[order],scores[order]
        result.append(ids[best].tolist())
    return result

def _load_faiss():
    try: import faiss
    except ImportError: return None,None
    try: version=faiss.__version__
    except AttributeError:
        try: version=importlib.metadata.version("faiss-cpu")
        except importlib.metadata.PackageNotFoundError: version="unknown"
    return faiss,version

def _build_index(faiss,vectors,index_type,hnsw_m):
    if index_type=="flat_ip": return faiss.IndexFlatIP(vectors.shape[1])
    if index_type=="hnsw_flat_ip": return faiss.IndexHNSWFlat(vectors.shape[1],hnsw_m,faiss.METRIC_INNER_PRODUCT)
    raise ValueError("index_type must be flat_ip or hnsw_flat_ip")

def benchmark_ann(*,artifact,queries,ks,index_type="hnsw_flat_ip",hnsw_m=32,ef_search=None,warmup=1,repeats=1,seed=42,eligible_mask=None,seen_indices=None,eligible_hash=None,seen_hash=None,ef_sweep=None,query_labels=None):
    if not ks or any(type(k) is not int or k<=0 for k in ks): raise ValueError("ks must contain positive integers")
    if warmup<0 or repeats<=0 or hnsw_m<=0 or (ef_search is not None and ef_search<=0): raise ValueError("invalid benchmark parameters")
    if ef_sweep is not None and (not ef_sweep or len(set(ef_sweep))!=len(ef_sweep)
            or any(type(e) is not int or e<=0 for e in ef_sweep) or ef_search is not None
            or index_type!="hnsw_flat_ip"):
        raise ValueError("Sweep requires distinct positive efSearch settings on HNSW only")
    if query_labels is not None and len(query_labels)!=len(queries):
        raise ValueError("Query label count mismatch")
    ids,vectors,manifest=load_benchmark_artifact(artifact); queries=np.asarray(queries,dtype=np.float32); max_k=max(ks)
    if queries.ndim!=2 or not len(queries) or queries.shape[1]!=vectors.shape[1]: raise ValueError("empty queries or dimension mismatch")
    if max_k>len(ids): raise ValueError("k exceeds catalog size")
    eligible=np.ones(len(ids),dtype=bool) if eligible_mask is None else np.asarray(eligible_mask,dtype=bool)
    if eligible.shape!=(len(ids),) or not eligible.any(): raise ValueError('invalid or empty eligible catalog mask')
    seen_indices=seen_indices or [set() for _ in range(len(queries))]
    exact=exact_topk(vectors,ids,queries,max_k,eligible_mask=eligible,seen_indices=seen_indices); faiss,version=_load_faiss()
    base={"status":"unavailable" if faiss is None else "complete","artifact":{"build_id":manifest.get("build_id"),"count":len(ids),"dimension":vectors.shape[1]},"parameters":{"index_type":index_type,"hnsw_m":hnsw_m,"ef_search":ef_search,"warmup":warmup,"repeats":repeats,"seed":seed,"ks":list(ks)},"environment":{"python":sys.version,"platform":platform.platform(),"numpy":np.__version__,"faiss":version},"git":_git_provenance(),"vector_bytes":int(vectors.nbytes),"query_count":len(queries)}
    base['artifact'].update({key: manifest.get(key) for key in ('manifest_sha256', 'vector_sha256', 'item_id_sha256', 'corpus_sha256', 'model', 'revision', 'text_protocol')})
    base['query_constraints']={'eligible_count': int(eligible.sum()), 'eligible_hash': eligible_hash, 'seen_hash': seen_hash, 'batch_size': 1}
    if faiss is None:
        base["reason"]="faiss is not installed; install the optional ANN environment to run this benchmark"; return base
    started=time.perf_counter(); index=_build_index(faiss,np.asarray(vectors,dtype=np.float32),index_type,hnsw_m); index.add(np.asarray(vectors,dtype=np.float32)); build=time.perf_counter()-started
    base.update(build_seconds=build,index_ntotal=int(index.ntotal))
    settings=ef_sweep or [ef_search if ef_search is not None else max(max_k*2,64)]
    runs={}
    for setting in settings:
        if index_type=="hnsw_flat_ip": index.hnsw.efSearch=setting
        runs[str(setting)]=_measure_index(index,ids,queries,eligible,seen_indices,exact,ks,warmup,repeats,query_labels)
    if ef_sweep is not None:
        base['parameters']['ef_sweep']=list(ef_sweep)
        base['runs']=runs
    else:
        base.update(next(iter(runs.values())))
    return base


def _measure_index(index,ids,queries,eligible,seen_indices,exact,ks,warmup,repeats,query_labels):
    max_k=max(ks)
    for _ in range(warmup):
        for query in queries: index.search(query[None, :], max_k)
    latencies=[]; result_ids=[]; incomplete_queries=0
    for _ in range(repeats):
        for query, excluded, reference in zip(queries, seen_indices, exact):
            target=len(reference)
            if target==0:
                latencies.append(0.0); result_ids.append([]); continue
            fetch=min(len(ids), max(target, target*4+len(excluded)))
            accepted=[]; started=time.perf_counter()
            while True:
                _,positions=index.search(query[None, :], fetch)
                accepted=[int(i) for i in positions[0] if i>=0 and eligible[int(i)] and int(i) not in excluded]
                if len(accepted)>=target or fetch>=len(ids): break
                fetch=min(len(ids), fetch*2)
            if len(accepted)<target: incomplete_queries+=1
            result_ids.append([str(ids[i]) for i in accepted[:target]])
            latencies.append(time.perf_counter()-started)
    recalls={}
    exact_repeated=exact*repeats
    for k in ks:
        vals=[len(set(a[:k])&set(e[:k]))/len(e[:k]) for a,e in zip(result_ids,exact_repeated) if e]
        recalls[str(k)]={key:float(fn(vals)) if vals else None for key,fn in [('mean',np.mean),('min',np.min),('max',np.max)]}
    rows=[]
    groups={}
    for i,reference in enumerate(exact):
        times=latencies[i::len(queries)]
        row=dict(query_labels[i]) if query_labels is not None else {'query_idx':i}
        row['latency']=_percentiles(times)
        row['recall']={str(k):float(np.mean([
            len(set(a[:k]).intersection(reference[:k]))/len(reference[:k])
            for a in result_ids[i::len(queries)]])) if reference else None for k in ks}
        rows.append(row)
        if 'segment' in row:
            groups.setdefault(row['segment'],[]).append(i)
    segments={}
    for segment,indices in groups.items():
        valid=[i for i in indices if exact[i]]
        segments[segment]={'query_count':len(indices),'recall_queries':len(valid),
            'recall':{str(k):float(np.mean([rows[i]['recall'][str(k)] for i in valid])) if valid else None for k in ks},
            'latency':_percentiles([t for i in indices for t in latencies[i::len(queries)]])}
    return {"latency":_percentiles(latencies),"latency_measurement":"serial filtered search per query including retries; encoder, build and warmup excluded","latency_samples":len(latencies),"throughput_queries_per_second":float(len(latencies)/sum(latencies)) if sum(latencies) else None,"recall":recalls,"incomplete_queries":incomplete_queries,"per_query":rows,"by_segment":segments}

def synthetic_queries(vectors,count,seed):
    if count<=0: raise ValueError("query count must be positive")
    rng=np.random.default_rng(seed); q=rng.normal(size=(count,vectors.shape[1])).astype(np.float32); q/=np.linalg.norm(q,axis=1,keepdims=True); return q
