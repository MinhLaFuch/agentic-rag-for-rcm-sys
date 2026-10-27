"""One fixed exploratory top-5 baseline guard on saved RRF pools; no retrieval."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import time
import uuid

import numpy as np
import yaml

from package.config import get_data_paths
from package.data.mapping import load_mappings
from package.tools.evaluation import next_experiment_dir,save_experiment
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash
from scripts.evaluation.sparse_content_replay import rrf
from scripts.evaluation.analyze_ranking_bottlenecks import _metrics


def guarded_order(pool,baseline,fused):
    if len(pool)!=len(set(pool)) or set(fused)!=set(pool) or len(fused)!=len(pool):
        raise ValueError('invalid fixed pool')
    prefix=[i for i in baseline[:5] if i in pool]
    if len(prefix)!=len(set(prefix)): raise ValueError('duplicate baseline prefix')
    return prefix+[i for i in fused if i not in prefix]


def compare(records,items,pilot_users,seed,samples,output):
    base={};seen=set();stats={};deltas=defaultdict(list);losses=defaultdict(Counter)
    with output.open('x',encoding='utf-8') as out:
        for r in records:
            key=(r['user_idx'],r['variant'])
            if key in seen: raise ValueError('duplicate stream')
            seen.add(key);u=r['user_idx']
            if r['variant']=='cf_1':
                base[u]={k:r[k] for k in ('targets','seeds','candidate_budget','ranked_ids')};continue
            if r['variant']!='cf_bm25_rrf' or u not in base: raise ValueError('baseline-first runtime RRF source required')
            b=base.pop(u)
            if any(b[k]!=r[k] for k in ('targets','seeds','candidate_budget')): raise ValueError('pair mismatch')
            pool=[i for i in r['candidates'] if i not in r['excluded_seen']+r['unscored_item_ids']]
            if len(pool)!=len(set(pool)) or len(r['candidates'])>r['candidate_budget']:raise ValueError('invalid pool/budget')
            start=time.perf_counter()
            if r['status']=='ok':
                fused=rrf(pool,r['source_candidates']['item_cf'],r['source_candidates']['bm25'])
                if fused[:10]!=r['ranked_ids']:raise ValueError('saved RRF reproduction mismatch')
                guarded=guarded_order(pool,b['ranked_ids'],fused)
            else:
                # Keep source failures in the denominator, do not invent fallback candidates.
                guarded=r['ranked_ids']
            elapsed=time.perf_counter()-start
            rankings={'cf_1':b['ranked_ids'],'saved_rrf':r['ranked_ids'],'baseline_top5_guard':guarded}
            gt=set(r['targets']); quality={name:_metrics(ids,gt,items,10) if gt else {} for name,ids in rankings.items()}
            groups=['overall','history:'+str(r['history_unique_items']),
                    'inspected_pilot' if u in pilot_users else 'remaining_development']
            for group in groups:
                for name,ids in rankings.items():
                    s=stats.setdefault((group,name),dict(users=0,eligible=0,q=Counter(),catalog=set()))
                    s['users']+=1;s['catalog'].update(ids[:10])
                    if gt:s['eligible']+=1;s['q'].update(quality[name])
                if gt:
                    old={items[i] for i in b['ranked_ids'][:10]}&gt
                    new={items[i] for i in guarded[:10]}&gt
                    losses[group].update(baseline_hit_users=int(bool(old)),guard_hit_users=int(bool(new)),
                        lost_hit_users=int(bool(old) and not new),gained_hit_users=int(not old and bool(new)),
                        lost_target_pairs=len(old-new),gained_target_pairs=len(new-old))
                    for ref in ('cf_1','saved_rrf'):
                        deltas[group,ref].append(quality['baseline_top5_guard']['ndcg@10']-quality[ref]['ndcg@10'])
            for name,ids in rankings.items():
                out.write(json.dumps(dict(user_idx=u,policy=name,targets=sorted(gt),ranked_ids_at10=ids[:10],
                    source_status=r['status'],ordering_seconds=elapsed if name=='baseline_top5_guard' else None))+'\n')
    if base or not seen:raise ValueError('incomplete source')
    result={};rng=np.random.default_rng(seed)
    for (group,name),s in stats.items():
        result.setdefault(group,{'variants':{},'hit_regressions':dict(losses[group])})['variants'][name]=dict(
            users=s['users'],eligible_users=s['eligible'],metrics={k:v/s['eligible'] for k,v in s['q'].items()} if s['eligible'] else {},
            catalog_coverage_at10=len(s['catalog'])/len(items))
    for (group,ref),d in deltas.items():
        vals,freq=np.unique(d,return_counts=True);n=len(d)
        boot=rng.multinomial(n,freq/n,size=samples)@vals/n
        result[group].setdefault('paired_ndcg10',{})[ref]=dict(mean_delta=float(np.mean(d)),
            familywise95_ci=np.percentile(boot,[1.25,98.75]).tolist(),improved=sum(x>0 for x in d),worse=sum(x<0 for x in d))
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--seed',type=int,default=42);ap.add_argument('--bootstrap-samples',type=int,default=10000);args=ap.parse_args()
    if args.bootstrap_samples<1000:ap.error('>=1000 bootstrap samples required')
    started=time.perf_counter();p=args.source
    hashes=json.loads((p/'artifact_hashes.json').read_text(encoding='utf-8'))
    def verify():
        for n in ('config.yaml','metrics.json','records.jsonl','requests.jsonl'):
            if file_hash(p/n)!=hashes[n]:raise ValueError('source hash mismatch')
    verify();cfg=yaml.safe_load((p/'config.yaml').read_text(encoding='utf-8'));d=cfg['run']['dataset']
    if d['eval_on']!='validation':raise ValueError('validation only')
    paths=get_data_paths(d['tag']);users,items=load_mappings(paths.mapped_dir)
    if mapping_hash(users)!=d['user_mapping_hash'] or mapping_hash(items)!=d['mapping_hash']:raise ValueError('mapping mismatch')
    root=paths.experiments_dir/'sparse_guard_replay';root.mkdir(parents=True,exist_ok=True)
    staging=root/('_staging_'+uuid.uuid4().hex);staging.mkdir()
    with (p/'records.jsonl').open(encoding='utf-8') as f:
        metrics=compare(map(json.loads,f),items,set(cfg['config']['identity'].get('pilot_user_ids',[])),args.seed,args.bootstrap_samples,staging/'replays.jsonl')
    original=json.loads((p/'metrics.json').read_text(encoding='utf-8'))
    for new,old in [('cf_1','cf_1'),('saved_rrf','cf_bm25_rrf')]:
        for name,value in metrics['overall']['variants'][new]['metrics'].items():
            if not np.isclose(value,original['variants'][old]['metrics'][name],atol=1e-13,rtol=0):raise ValueError('baseline metric mismatch')
    verify();metrics['qualification']='exploratory inspected validation; no production selection, no serving latency claim; source error retained'
    config=dict(source=str(p.resolve()),source_hashes=hashes,policy='baseline top5 in original order, then source RRF60; no pool additions',
        primary_cohort='remaining_development',comparisons=2,bootstrap_samples=args.bootstrap_samples,production_changed=False)
    # save_experiment requires a fresh path; keep the already written replay in a child staging directory.
    publication=staging/'publication'
    save_experiment(publication,config=config,metrics=metrics,seed=args.seed,dataset_info=d,runtime_seconds=time.perf_counter()-started,write_readme=False)
    (staging/'replays.jsonl').rename(publication/'replays.jsonl')
    (publication/'artifact_hashes.json').write_text(json.dumps({n:file_hash(publication/n) for n in ('config.yaml','metrics.json','replays.jsonl')},indent=2),encoding='utf-8')
    output=next_experiment_dir(root);publication.rename(output);staging.rmdir()
    print('Saved:',output,flush=True);print(json.dumps(metrics['remaining_development'],indent=2),flush=True)


if __name__=='__main__':main()
