"""Fixed-sample, read-only CF link and exact BM25 rank probe; never refits."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import random
import sqlite3
import time
import uuid

import numpy as np
import pyarrow.parquet as pq
import scipy.sparse as sp
import yaml

from package.config import get_data_paths
from package.data.mapping import load_mappings
from package.tools.evaluation import next_experiment_dir,save_experiment
from package.tools.evaluation.classify_cf_link import classify_cf_link
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash


def probe(source,corpus,model,sample_size,seed):
    started=time.perf_counter();hashes=json.loads((source/'artifact_hashes.json').read_text(encoding='utf-8'))
    def verify():
        for n in ('config.yaml','metrics.json','records.jsonl','requests.jsonl'):
            if file_hash(source/n)!=hashes[n]:raise ValueError('source hash mismatch')
    verify();cfg=yaml.safe_load((source/'config.yaml').read_text(encoding='utf-8'));d=cfg['run']['dataset']
    if d['eval_on']!='validation':raise ValueError('validation only')
    paths=get_data_paths(d['tag']);users,items=load_mappings(paths.mapped_dir);inverse={v:k for k,v in items.items()}
    if mapping_hash(users)!=d['user_mapping_hash'] or mapping_hash(items)!=d['mapping_hash']:raise ValueError('mapping mismatch')
    train=paths.split_path('train');train_hash=file_hash(train)
    if train_hash!=d['split_files']['train']['sha256']:raise ValueError('train hash mismatch')
    model_hash=file_hash(model)
    expected={e['path']:e['sha256'] for e in cfg['config']['identity']['source']}
    if expected.get(str(model.resolve()))!=model_hash:raise ValueError('model differs from source runtime')
    sim=sp.load_npz(model).tocsr();corpus_hash=file_hash(corpus)
    candidates=[]
    for line in (source/'records.jsonl').open(encoding='utf-8'):
        r=json.loads(line)
        if r['variant']=='cf_bm25_rrf' and r['status']=='ok':
            missed=sorted(set(r['targets'])-{items[i] for i in r['candidates']})
            if missed:candidates.append((r['user_idx'],missed))
    rng=random.Random(seed);chosen=rng.sample(sorted(candidates),min(sample_size,len(candidates)))
    targets={u:rng.choice(missed) for u,missed in chosen};selected={}
    for line in (source/'records.jsonl').open(encoding='utf-8'):
        r=json.loads(line)
        if r['variant']=='cf_bm25_rrf' and r['user_idx'] in targets:selected[r['user_idx']]=r
    focus={items[r['seeds'][0]] for r in selected.values()}|set(targets.values());support=defaultdict(set)
    for batch in pq.ParquetFile(train).iter_batches(columns=['user_idx','item_idx'],batch_size=500000):
        u=batch.column(0).to_numpy();i=batch.column(1).to_numpy();mask=np.isin(i,list(focus))
        for a,b in zip(u[mask],i[mask]):support[int(b)].add(int(a))
    conn=sqlite3.connect(corpus.resolve().as_uri()+'?mode=ro',uri=True);conn.execute('PRAGMA query_only=ON')
    deadline=time.monotonic()+5;conn.set_progress_handler(lambda:int(time.monotonic()>deadline),10000)
    counts=Counter();details=[]
    for pos,(u,_) in enumerate(chosen):
        r=selected[u];s=items[r['seeds'][0]];t=targets[u];row=sim.getrow(s)
        cutoff=float(row.data.min()) if row.nnz else 0.
        co=len(support[s]&support[t]);cf=classify_cf_link(len(support[s]),len(support[t]),co,t in row.indices,cutoff)
        event=next(e for e in r['source_events'] if e['tool']=='SemanticSearchTool');tokens=event['data']['query_tokens']
        match=' OR '.join('"'+x+'"' for x in tokens);exclude=event['args']['filters']['exclude_item_ids']
        where='items.item_id NOT IN ('+','.join('?' for _ in exclude)+')' if exclude else '1=1'
        base=f'FROM items_fts JOIN items ON items.rowid=items_fts.rowid WHERE items_fts MATCH ? AND {where}'
        params=[match,*exclude];deadline=time.monotonic()+5
        top=conn.execute(f'SELECT items.item_id,-bm25(items_fts) score {base} ORDER BY score DESC,items.rating_number DESC,items.item_id LIMIT 25',params).fetchall()
        if [x[0] for x in top]!=[x['item_id'] for x in event['data']['candidates']]:raise ValueError('diagnostic corpus BM25 top25 differs from source')
        if not np.allclose([x[1] for x in top],[x['score'] for x in event['data']['candidates']],rtol=1e-12,atol=1e-12):raise ValueError('diagnostic BM25 scores differ')
        # Materialize scores before window ranking: BM25 cannot execute in a window context.
        sql=f'''WITH scored AS MATERIALIZED (SELECT items.item_id,items.rating_number,-bm25(items_fts) score {base}),
        ranked AS (SELECT item_id,score,ROW_NUMBER() OVER (ORDER BY score DESC,rating_number DESC,item_id) position FROM scored)
        SELECT position,score FROM ranked WHERE item_id=?'''
        deadline=time.monotonic()+5;begin=time.perf_counter()
        try:
            found=conn.execute(sql,[*params,inverse[t]]).fetchone()
            reason='outside_top25' if found and found[0]>25 else 'inside_top25' if found else 'no_lexical_match'
        except sqlite3.OperationalError as exc:
            if 'interrupt' not in str(exc).lower():raise
            found=None;reason='rank_probe_timeout'
        counts['cf:'+cf['reason']]+=1;counts['bm25:'+reason]+=1
        details.append(dict(user_idx=u,seed_item=r['seeds'][0],target_item=inverse[t],history_unique_items=r['history_unique_items'],
            train_seed_users=len(support[s]),train_target_users=len(support[t]),cooccurrence_users=co,cache_cutoff=cutoff,cf=cf,
            query=r['query_provenance']['sent'],bm25_reason=reason,bm25_rank=found[0] if found else None,
            bm25_score=found[1] if found else None,rank_probe_seconds=time.perf_counter()-begin))
        print(f'[probe] {pos+1}/{len(chosen)} CF={cf["reason"]} BM25={reason}',flush=True)
    conn.close();verify()
    if file_hash(train)!=train_hash or file_hash(model)!=model_hash or file_hash(corpus)!=corpus_hash:raise ValueError('input changed')
    return dict(counts=dict(counts),details=details),d,dict(source=str(source.resolve()),source_hashes=hashes,
        train_sha256=train_hash,model_sha256=model_hash,corpus_sha256=corpus_hash,sample_size=len(chosen),seed=seed,
        sampling='uniform users with missed targets and successful saved hybrid; one uniformly sampled missed target per user',
        scope='conditional diagnosis only; target used to inspect outcomes, never to construct query; failures excluded by design',
        metadata_check='sample top25 IDs and scores must reproduce source; not full metadata provenance equivalence'),time.perf_counter()-started


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('source','corpus','item-knn'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--users',type=int,default=32);ap.add_argument('--seed',type=int,default=42);a=ap.parse_args()
    if not 1<=a.users<=100:ap.error('diagnostic sample must be 1..100 users')
    metrics,d,cfg,seconds=probe(a.source,a.corpus,a.item_knn,a.users,a.seed)
    root=get_data_paths(d['tag']).experiments_dir/'sparse_retrieval_probe';root.mkdir(parents=True,exist_ok=True)
    staging=root/('_staging_'+uuid.uuid4().hex)
    save_experiment(staging,config=cfg,metrics=metrics,seed=a.seed,dataset_info=d,runtime_seconds=seconds,write_readme=False)
    (staging/'artifact_hashes.json').write_text(json.dumps({n:file_hash(staging/n) for n in ('config.yaml','metrics.json')},indent=2),encoding='utf-8')
    out=next_experiment_dir(root);staging.rename(out);print('Saved:',out,metrics['counts'],flush=True)


if __name__=='__main__':main()
