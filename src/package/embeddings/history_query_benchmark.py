"""Prepare dense ANN queries from a completed, frozen retrieval matrix."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np

def _digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def _query_vector(encoder, components, dimension):
    texts=[c.get('text','') for c in components if c.get('text','').strip()]
    if not texts: return None
    weights=np.asarray([c.get('weight',1.) for c in components if c.get('text','').strip()],dtype=np.float32)
    vectors=np.asarray(encoder.encode(texts),dtype=np.float32)
    if vectors.shape!=(len(texts),dimension) or not np.isfinite(vectors).all(): raise ValueError('Invalid history query embeddings')
    norms=np.linalg.norm(vectors,axis=1,keepdims=True)
    if np.any(norms<=1e-9): raise ValueError('Zero history query embedding')
    vectors/=norms
    query=np.average(vectors,axis=0,weights=weights)
    norm=np.linalg.norm(query)
    if norm<=1e-9: raise ValueError('History query centroid is zero')
    return query/norm

def load_history_validation_queries(*, matrix_dir, encoder, item_ids, dimension, mode='latest_title', segment=None, budget=None):
    """Validate matrix provenance and produce normalized query vectors plus seen-index sets."""
    root=Path(matrix_dir)
    completion=json.loads((root/'artifact_hashes.json').read_text(encoding='utf-8'))
    if completion.get('status')!='complete': raise ValueError('History matrix is not complete')
    config=json.loads((root/'config.json').read_text(encoding='utf-8'))
    if config.get('version')!=1 or config.get('target_policy')!='novel targets; targets never used for query or fusion':
        raise ValueError('Unsupported or target-informed history matrix protocol')
    required={'config.json','candidate_sets.jsonl','frozen.json','ranked.jsonl','metrics.json'}
    if set(completion['hashes'])!=required:
        raise ValueError('Incomplete matrix checksum inventory')
    if config['provenance']['protocol']['item_knn']['eval_on']!='validation':
        raise ValueError('Expected a validation matrix')
    for name,expected in completion['hashes'].items():
        if _digest(root/name)!=expected: raise ValueError(f'History matrix artifact checksum mismatch: {name}')
    frozen=json.loads((root/'frozen.json').read_text(encoding='utf-8'))
    if _digest(root/'candidate_sets.jsonl')!=frozen.get('candidate_sets_sha256'):
        raise ValueError('Frozen candidate set checksum mismatch')
    ids=np.asarray(item_ids)
    queries=[]; seen_sets=[]; users=[]; query_provenance=[]
    selected={}
    with (root/'candidate_sets.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row.get('mode')!=mode or (segment is not None and row.get('segment')!=segment): continue
            if budget is not None and row.get('budget')!=budget: continue
            user=int(row['user_idx'])
            if user in selected: continue
            query=row.get('query',{})
            if query.get('mode')!=mode or query.get('target_used') is not False:
                raise ValueError('History query mode/provenance mismatch')
            components=query.get('components',[])
            seen_names=set(row['seen'])
            if any(c['item_id'] not in seen_names or c['timestamp']>=query['cutoff_exclusive']
                   for c in components):
                raise ValueError('Frozen query contains an item outside pre-cutoff history')
            q=_query_vector(encoder,components,dimension)
            if q is None: continue
            seen=set()
            for name in seen_names:
                i=int(ids.searchsorted(name))
                if i==len(ids) or ids[i]!=name: raise ValueError(f'Seen item missing from embedding mapping: {name}')
                seen.add(i)
            selected[user]=(q,seen,{**query,'segment':row['segment']})
    for user,(query,seen,provenance) in sorted(selected.items()):
        queries.append(query); seen_sets.append(seen); users.append(user); query_provenance.append(provenance)
    if not queries: raise ValueError('No eligible history queries found in frozen matrix')
    return np.asarray(queries,dtype=np.float32),seen_sets,users,query_provenance

def eligible_mask_from_ids(item_ids, eligible_ids):
    eligible=set(map(str,eligible_ids))
    return np.fromiter((str(item) in eligible for item in item_ids),dtype=bool,count=len(item_ids))

def hash_eligible_ids(item_ids,mask):
    payload='\n'.join(str(item) for item,ok in zip(item_ids,mask) if ok).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()

def hash_seen_sets(seen_sets):
    payload='\n'.join(','.join(map(str,sorted(s))) for s in seen_sets).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
