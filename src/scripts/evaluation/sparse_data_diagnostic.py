"""Diagnose fixed sparse requests without retrieval, fitting, or dataset changes."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import time
import uuid

import numpy as np
import pyarrow.parquet as pq
import yaml

from package.config import get_data_paths
from package.data.mapping import load_mappings
from package.tools.evaluation import next_experiment_dir, save_experiment
from package.tools.evaluation.normalize_query_text import normalize_query_text
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash
from package.tools.retrieval.tokenize_search_query import tokenize_search_query


def diagnose(source, corpus_path):
    started=time.perf_counter()
    manifest=json.loads((source/'artifact_hashes.json').read_text(encoding='utf-8'))
    for name in ('config.yaml','metrics.json','records.jsonl','requests.jsonl'):
        if file_hash(source/name)!=manifest[name]: raise ValueError('source hash mismatch')
    cfg=yaml.safe_load((source/'config.yaml').read_text(encoding='utf-8')); d=cfg['run']['dataset']
    if d['eval_on']!='validation': raise ValueError('validation only')
    paths=get_data_paths(d['tag']); users,items=load_mappings(paths.mapped_dir); inverse={v:k for k,v in items.items()}
    if mapping_hash(users)!=d['user_mapping_hash'] or mapping_hash(items)!=d['mapping_hash']: raise ValueError('mapping mismatch')
    train=paths.split_path('train'); train_hash=file_hash(train)
    if train_hash!=d['split_files']['train']['sha256']: raise ValueError('train hash mismatch')
    requests={}
    for line in (source/'requests.jsonl').open(encoding='utf-8'):
        r=json.loads(line)
        if r['user_idx'] in requests: raise ValueError('duplicate request')
        requests[r['user_idx']]=r
    if set(requests)!=set(cfg['config']['sampled_user_ids']): raise ValueError('sample mismatch')
    focus={i for r in requests.values() for i in r['targets']}
    support=defaultdict(set); event_counts=Counter()
    print('[data] counting distinct train users per target item',flush=True)
    for b in pq.ParquetFile(train).iter_batches(columns=['user_idx','item_idx'],batch_size=500000):
        u=b.column(0).to_numpy(); i=b.column(1).to_numpy(); mask=np.isin(i,list(focus))
        for user,item in zip(u[mask],i[mask]): support[int(item)].add(int(user));event_counts[int(item)]+=1
    corpus_hash=file_hash(corpus_path)
    conn=sqlite3.connect(corpus_path.resolve().as_uri()+'?mode=ro',uri=True)
    conn.execute('PRAGMA query_only=ON')
    title={}
    names=[inverse[i] for i in focus]
    for start in range(0,len(names),400):
        chunk=names[start:start+400]
        title.update(conn.execute('SELECT item_id,title FROM items WHERE item_id IN ('+','.join('?' for _ in chunk)+')',chunk))
    counts=defaultdict(Counter); baselines={}; seed_meta=Counter(); seen=set()
    for line in (source/'records.jsonl').open(encoding='utf-8'):
        r=json.loads(line); u=r['user_idx']
        if (u,r['variant']) in seen: raise ValueError('duplicate source record')
        seen.add((u,r['variant']))
        if r['variant']=='cf_1': baselines[u]=r['ranked_ids'];continue
        if r['variant']!='cf_bm25_rrf' or u not in baselines: raise ValueError('expected baseline-first RRF stream')
        if r['targets']!=requests[u]['targets']: raise ValueError('request target mismatch')
        seed_meta['requests']+=1
        seed_meta['unsearchable_seed_title']+=not bool(tokenize_search_query(normalize_query_text(r['query_provenance']['raw'] or '', 'ascii_fold')))
        seed=r['seeds'][0]; stored=conn.execute('SELECT title FROM items WHERE item_id=?',(seed,)).fetchone()
        seed_meta['seed_title_matches_diagnostic_corpus']+=bool(stored and stored[0]==r['query_provenance']['raw'])
        history_domains={inverse[x['item_idx']].split('::',1)[0] for x in requests[u]['history']}
        pool=set(r['candidates']); ranked=set(r['ranked_ids'][:10]); old=set(baselines.pop(u)[:10])
        for item in set(r['targets']):
            name=inverse[item]; n=len(support[item]); bucket='0' if n==0 else '1_4' if n<5 else '5_19' if n<20 else '20_plus'
            domains=name.split('::',1)[0]
            for group in ('overall','support:'+bucket,'history:'+str(r['history_unique_items']),'domain:'+domains):
                c=counts[group];c['target_pairs']+=1;c['train_support_'+bucket]+=1
                c['cross_history_domain']+=domains not in history_domains
                c['missing_metadata_snapshot']+=name not in title
                c['unsearchable_target_title_snapshot']+=not bool(tokenize_search_query(normalize_query_text(title.get(name) or '', 'ascii_fold')))
                c['retrieved']+=name in pool;c['not_retrieved']+=name not in pool
                c['top10']+=name in ranked;c['baseline_top10']+=name in old
                c['retrieved_below_top10']+=name in pool and name not in ranked
    conn.close()
    if baselines or len(seen)!=2*len(requests): raise ValueError('incomplete paired records')
    for name,h in manifest.items():
        if file_hash(source/name)!=h: raise ValueError('source changed')
    if file_hash(train)!=train_hash or file_hash(corpus_path)!=corpus_hash: raise ValueError('diagnostic input changed')
    return (dict(counts={k:dict(v) for k,v in counts.items()},seed_metadata=dict(seed_meta),
        users=len(requests),unique_target_items=len(focus),
        metadata_scope='separate current SQLite snapshot; seed-title agreement is checked, not full source metadata equivalence',
        support_definition='unique train (user,item) pairs; repeated events do not increase support',
        counting='micro novel target pairs per user; NOT macro user Recall@K'),d,
        dict(source=str(source.resolve()),source_hashes=manifest,train_sha256=train_hash,
             diagnostic_corpus=str(corpus_path.resolve()),diagnostic_corpus_sha256=corpus_hash,
             selection='unchanged saved 5000 sparse requests, no core filtering, no target-based query construction'),time.perf_counter()-started)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--corpus',type=Path,required=True);args=ap.parse_args()
    metrics,d,config,seconds=diagnose(args.source,args.corpus)
    root=get_data_paths(d['tag']).experiments_dir/'sparse_data_diagnostic'
    root.mkdir(parents=True,exist_ok=True); staging=root/('_staging_'+uuid.uuid4().hex)
    save_experiment(staging,config=config,metrics=metrics,seed=42,dataset_info=d,runtime_seconds=seconds,write_readme=False)
    (staging/'artifact_hashes.json').write_text(json.dumps({n:file_hash(staging/n) for n in ('config.yaml','metrics.json')},indent=2),encoding='utf-8')
    out=next_experiment_dir(root);staging.rename(out);print('Saved:',out,flush=True)
    print(json.dumps(metrics,indent=2),flush=True)


if __name__=='__main__':main()
