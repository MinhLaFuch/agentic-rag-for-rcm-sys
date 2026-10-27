"""Source-rank RRF diagnostic for saved sparse CF/BM25 pools; no retrieval."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import time
import uuid

import numpy as np
import yaml

from package.config import get_data_paths
from package.data.mapping import load_mappings
from package.tools.evaluation import next_experiment_dir, save_experiment
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash
from scripts.evaluation.analyze_ranking_bottlenecks import _metrics


def rrf(pool, cf, bm25):
    """Equal source weights, fixed RRF constant 60; stable pool-order ties."""
    scores=dict.fromkeys(pool,0.)
    for source in (cf,bm25):
        if len(source)!=len(set(source)):
            raise ValueError("duplicate source candidates")
        for rank,item in enumerate(source,1):
            if item in scores: scores[item]+=1/(60+rank)
    return sorted(pool,key=lambda item:-scores[item])


def compare(records, items, seed, samples, output):
    groups=defaultdict(dict)
    for row in records:
        u,v=row['user_idx'],row['variant']
        if v not in ('cf_1','cf_bm25') or v in groups[u]:
            raise ValueError('unknown or duplicate source variant')
        groups[u][v]=row
    if not groups: raise ValueError('empty source')
    stats={}; segments={}; deltas=defaultdict(list)
    with output.open('x',encoding='utf-8') as stream:
        for u,g in groups.items():
            if set(g)!={'cf_1','cf_bm25'}: raise ValueError('incomplete pair')
            base,hybrid=g['cf_1'],g['cf_bm25']
            for key in ('targets','seeds','history_unique_items','candidate_budget'):
                if base[key]!=hybrid[key]: raise ValueError('source pair mismatch: '+key)
            for row in (base,hybrid):
                if row['status']!='ok' or row['error'] or row['metadata_missing_ids']:
                    raise ValueError('successful metadata-complete source required')
                if len(row['candidates'])!=len(set(row['candidates'])) or len(row['candidates'])>row['candidate_budget']:
                    raise ValueError('invalid candidate budget/deduplication')
            events=hybrid['source_events']
            cf=next(e for e in events if e['tool']=='ItemCFTool')
            bm=next(e for e in events if e['tool']=='SemanticSearchTool')
            if not cf['ok'] or not bm['ok']: raise ValueError('source tool error')
            cfids=[r['item_id'] for r in cf['data']['candidates']]
            bmids=[r['item_id'] for r in bm['data']['candidates']]
            if cfids!=base['candidates']: raise ValueError('CF control changed')
            if list(dict.fromkeys(cfids+bmids))!=hybrid['candidates']:
                raise ValueError('source union mismatch')
            excluded=set(hybrid['excluded_seen']+hybrid['unscored_item_ids'])
            pool=[i for i in hybrid['candidates'] if i not in excluded]
            if len(pool)!=hybrid['eligible_candidates']: raise ValueError('eligible pool mismatch')
            start=time.perf_counter(); fused=rrf(pool,cfids,bmids); elapsed=time.perf_counter()-start
            rankings={'cf_1':base['ranked_ids'],'hybrid_saved':hybrid['ranked_ids'],'source_rrf60':fused}
            gt=set(base['targets']); bucket=str(base['history_unique_items'])
            quality={}
            for name,ranked in rankings.items():
                allowed=base['candidates'] if name=='cf_1' else pool
                if len(ranked)!=len(set(ranked)) or not set(ranked)<=set(allowed):
                    raise ValueError('ranking outside eligible source')
                q=_metrics(ranked,gt,items,10) if gt else {}
                quality[name]=q
                for s in (stats.setdefault(name,dict(users=0,eligible=0,quality=Counter(),catalog=set())),
                          segments.setdefault(bucket,{}).setdefault(name,dict(users=0,eligible=0,quality=Counter(),catalog=set()))):
                    s['users']+=1
                    if gt: s['eligible']+=1; s['quality'].update(q)
                    s['catalog'].update(ranked[:10])
                stream.write(json.dumps(dict(user_idx=u,policy=name,targets=sorted(gt),history_unique_items=int(bucket),
                    ranked_ids_at10=ranked[:10],pool_size=len(allowed),
                    ordering_seconds=elapsed if name=='source_rrf60' else None))+ '\n')
            if gt:
                for reference in ('cf_1','hybrid_saved'):
                    deltas[reference].append(quality['source_rrf60']['ndcg@10']-quality[reference]['ndcg@10'])
    def finish(s):
        return dict(users=s['users'],eligible_users=s['eligible'],empty_ground_truth=s['users']-s['eligible'],
            metrics={k:v/s['eligible'] for k,v in s['quality'].items()} if s['eligible'] else {},
            catalog_coverage_at10=len(s['catalog'])/len(items),unique_top10=len(s['catalog']))
    result={n:finish(s) for n,s in stats.items()}; rng=np.random.default_rng(seed)
    paired={}
    for ref,d in deltas.items():
        values,freq=np.unique(d,return_counts=True); n=len(d)
        means=rng.multinomial(n,freq/n,size=samples)@values/n
        paired[ref]=dict(mean_delta=float(np.mean(d)),familywise95_ci=np.percentile(means,[1.25,98.75]).tolist(),
            improved=sum(x>0 for x in d),worse=sum(x<0 for x in d))
    guard={}
    for ref,b in result.items():
        if ref=='source_rrf60' or not b['metrics']: continue
        m=result['source_rrf60']['metrics']; old=b['metrics']
        guard[ref]=dict(ndcg_effect=m['ndcg@10']-old['ndcg@10']>=max(.0005,.1*old['ndcg@10']),
            paired_lower_positive=paired[ref]['familywise95_ci'][0]>0,
            recall=m['recall@10']>=.95*old['recall@10'],hit=m['hit_rate@10']>=.95*old['hit_rate@10'],
            coverage=result['source_rrf60']['catalog_coverage_at10']>=.8*b['catalog_coverage_at10'],runtime_latency=None)
    return dict(variants=result,history_segments={k:{n:finish(s) for n,s in v.items()} for k,v in segments.items()},
        paired_ndcg10=paired,development_guardrails=guard,
        latency_scope='ordering only in replays.jsonl; no retrieval, metadata fetch or serving latency measured')


def run(args):
    started=time.perf_counter(); source=args.source
    hashes=json.loads((source/'artifact_hashes.json').read_text(encoding='utf-8'))
    required={'config.yaml','metrics.json','records.jsonl','requests.jsonl'}
    if not required<=hashes.keys(): raise ValueError('incomplete source manifest')
    def verify():
        for name,h in hashes.items():
            path=(source/name).resolve()
            if path.parent!=source.resolve() or file_hash(path)!=h: raise ValueError('source hash/path mismatch')
    verify(); cfg=yaml.safe_load((source/'config.yaml').read_text(encoding='utf-8')); d=cfg['run']['dataset']
    if d['eval_on']!='validation' or cfg['config']['identity']['retrieval_mode']!='cf_bm25':
        raise ValueError('validation CF/BM25 source required')
    paths=get_data_paths(d['tag']); users,items=load_mappings(paths.mapped_dir)
    if mapping_hash(users)!=d['user_mapping_hash'] or mapping_hash(items)!=d['mapping_hash']: raise ValueError('mapping mismatch')
    root=paths.experiments_dir/'sparse_content_replay'; root.mkdir(parents=True,exist_ok=True)
    staging=root/('_staging_'+uuid.uuid4().hex)
    save_experiment(staging,config=dict(source=str(source.resolve()),source_hashes=hashes,
        policy='equal-source RRF60; stable union-order ties; no target-dependent weights',
        comparisons=2,bootstrap_samples=args.bootstrap_samples,ndcg_absolute_min=.0005,ndcg_relative_min=.1,
        recall_hit_retention_min=.95,coverage_retention_min=.8,
        interpretation='source retrieval ranks, NOT full-history CF scorer scores; saved hybrid is fixed-pool control',
        production_changed=False),metrics={},seed=args.seed,dataset_info=d,runtime_seconds=0,write_readme=False)
    with (source/'records.jsonl').open(encoding='utf-8') as f:
        result=compare(map(json.loads,f),items,args.seed,args.bootstrap_samples,staging/'replays.jsonl')
    original=json.loads((source/'metrics.json').read_text(encoding='utf-8'))
    for new,old in [('cf_1','cf_1'),('hybrid_saved','cf_bm25')]:
        for metric,value in result['variants'][new]['metrics'].items():
            if not np.isclose(value,original['variants'][old]['metrics'][metric],atol=1e-13,rtol=0):
                raise ValueError('saved baseline reproduction mismatch')
    verify(); result['runtime_seconds']=time.perf_counter()-started
    result['qualification']='exploratory inspected pilot; untouched larger confirmation and serving latency required'
    (staging/'metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    manifest=yaml.safe_load((staging/'config.yaml').read_text(encoding='utf-8'))
    manifest['run']['runtime_seconds']=result['runtime_seconds']
    (staging/'config.yaml').write_text(yaml.safe_dump(manifest,sort_keys=False),encoding='utf-8')
    (staging/'artifact_hashes.json').write_text(json.dumps({n:file_hash(staging/n) for n in ('config.yaml','metrics.json','replays.jsonl')},indent=2),encoding='utf-8')
    output=next_experiment_dir(root); staging.rename(output); print('Saved content replay:',output,flush=True)
