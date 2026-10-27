"""Replay recorded recency priorities or source-rank CF/BM25 RRF; no retrieval/fit.

This is NOT a recency-weighted model scorer: scores outside the saved top-10
are unavailable. Recency mode tests prefix priorities; content mode tests
equal-source RRF60 using recorded retrieval ranks, not imputed model scores.
No metadata fetch or production latency is claimed. Writes JSON/YAML only.
"""
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
from package.tools.evaluation.recent_priority_order import recent_priority_order
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash
from scripts.evaluation.analyze_ranking_bottlenecks import _metrics

POLICIES=("baseline","latest_top3_guard","latest_cf_first")


def _compare(source,items,seed,bootstrap_samples,output_file):
    donors={}; stats={}; deltas=defaultdict(list); segments={}; loss=Counter(); counts=Counter(); observed=set()
    with source.open(encoding="utf-8") as stream,output_file.open("x",encoding="utf-8") as out:
        for line in stream:
            row=json.loads(line); u,n=row["user_idx"],row["seed_count"]
            if (u,n) in observed: raise ValueError("duplicate source user/variant")
            observed.add((u,n))
            if n==1:
                donors[u]=row
                continue
            if n not in (2,4) or u not in donors: raise ValueError("source needs baseline-first seed 1/2/4 streams")
            donor=donors[u]
            if row["targets"]!=donor["targets"] or row["history_unique_items"]!=donor["history_unique_items"]:
                raise ValueError("source ground truth/history mismatch")
            if row["error"] or donor["error"] or row["metadata_missing_ids"] or donor["metadata_missing_ids"]:
                raise ValueError("replay requires successful, metadata-complete source records")
            if row["candidate_budget"]!=donor["candidate_budget"]: raise ValueError("source budgets differ")
            excluded=set(row["excluded_seen"]+row["unscored_item_ids"])
            pool=[i for i in row["candidates"] if i not in excluded]
            if len(pool)!=row["eligible_candidates"] or len(pool)!=len(set(pool)):
                raise ValueError("effective-pool mismatch")
            targets=set(row["targets"]); counts[n]+=1
            available={items[i] for i in pool}&targets
            old_hit={items[i] for i in donor["ranked_ids"][:10]}&targets
            now_hit={items[i] for i in row["ranked_ids"][:10]}&targets
            loss[n,"baseline_hit_pairs_outside_pool"]+=len(old_hit-{items[i] for i in pool})
            loss[n,"baseline_hit_pairs_in_pool_below10"]+=len((old_hit&{items[i] for i in pool})-now_hit)
            loss[n,"target_pairs_in_pool"]+=len(available)
            for policy in POLICIES:
                start=time.perf_counter()
                ranked=(row["ranked_ids"] if policy=="baseline" else
                        recent_priority_order(pool,row["ranked_ids"],donor["ranked_ids"],donor["candidates"],policy))
                elapsed=time.perf_counter()-start
                if policy!="baseline" and set(ranked)!=set(pool): raise ValueError("replay changed pool")
                key=(n,policy)
                s=stats.setdefault(key,dict(users=0,eligible=0,quality=Counter(),catalog=set(),seconds=[],changed=0,oracle=0.))
                s["users"]+=1; s["seconds"].append(elapsed); s["changed"]+=ranked[:10]!=row["ranked_ids"][:10]
                bucket=segments.setdefault(str(row["history_unique_items"]),{}).setdefault(f"{n}:{policy}",dict(users=0,eligible=0,quality=Counter()))
                bucket["users"]+=1
                if targets:
                    s["eligible"]+=1; bucket["eligible"]+=1
                    q=_metrics(ranked,targets,items,10)
                    s["quality"].update(q); bucket["quality"].update(q); s["catalog"].update(ranked[:10])
                    s["oracle"]+=min(10,len(available))/len(targets)
                    baseline=_metrics(row["ranked_ids"],targets,items,10)
                    deltas[key].append(q["ndcg@10"]-baseline["ndcg@10"])
                out.write(json.dumps(dict(user_idx=u,history_unique_items=row["history_unique_items"],seed_count=n,
                    policy=policy,targets=sorted(targets),ranked_ids_at10=ranked[:10],pool_size=len(pool),
                    replay_seconds=elapsed),ensure_ascii=False)+"\n")
    if not donors or counts[2]!=len(donors) or counts[4]!=len(donors): raise ValueError("incomplete source streams")
    rng=np.random.default_rng(seed); result={}
    for (n,policy),s in stats.items():
        eligible=s["eligible"]
        r=dict(users=s["users"],eligible_users=eligible,metrics={k:v/eligible for k,v in s["quality"].items()} if eligible else {},
               coverage_at10=len(s["catalog"])/len(items),unique_top10=len(s["catalog"]),changed_rankings=s["changed"],
               oracle_recall10_fixed_pool=s["oracle"]/eligible if eligible else None,
               ordering_only_mean_seconds=float(np.mean(s["seconds"])))
        if policy!="baseline" and eligible:
            d=np.asarray(deltas[n,policy]); values,freq=np.unique(d,return_counts=True)
            means=rng.multinomial(eligible,freq/eligible,size=bootstrap_samples) @ values / eligible
            r["paired_ndcg10"]={"mean_delta":float(d.mean()),"familywise95_ci":np.percentile(means,[1.25,98.75]).tolist(),
                                "improved":int((d>0).sum()),"worse":int((d<0).sum())}
        result.setdefault(str(n),{})[policy]=r
    for n,policies in result.items():
        base=policies["baseline"]
        for policy,r in policies.items():
            if policy=="baseline" or not r["metrics"]: continue
            bm,rm=base["metrics"],r["metrics"]
            r["development_guardrails"]={"ndcg_effect":rm["ndcg@10"]-bm["ndcg@10"]>=max(.0005,.1*bm["ndcg@10"]),
                "paired_lower_positive":r["paired_ndcg10"]["familywise95_ci"][0]>0,
                "recall":rm["recall@10"]>=.95*bm["recall@10"],"hit":rm["hit_rate@10"]>=.95*bm["hit_rate@10"],
                "coverage":r["coverage_at10"]>=.8*base["coverage_at10"],"runtime_latency":None}
    for variants in segments.values():
        for s in variants.values(): s["metrics"]={k:v/s["eligible"] for k,v in s.pop("quality").items()} if s["eligible"] else {}
    return dict(comparison=result,history_segments=segments,losses={str(n):{key:value for (count,key),value in loss.items() if count==n} for n in (2,4)})


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--mode",choices=("recency","content"),default="recency")
    ap.add_argument("--seed",type=int,default=42)
    ap.add_argument("--bootstrap-samples",type=int,default=10000)
    args=ap.parse_args()
    if args.bootstrap_samples<1000: ap.error("bootstrap-samples must be >=1000")
    if args.mode=="content":
        from scripts.evaluation.sparse_content_replay import run
        return run(args)
    started=time.perf_counter(); cfg=yaml.safe_load((args.source/"config.yaml").read_text(encoding="utf-8"))
    dataset=cfg["run"]["dataset"]
    if dataset["eval_on"]!="validation": raise ValueError("validation only")
    hashes=json.loads((args.source/"artifact_hashes.json").read_text())
    for name,h in hashes.items():
        if file_hash(args.source/name)!=h: raise ValueError("source artifact hash mismatch")
    paths=get_data_paths(dataset["tag"]); users,items=load_mappings(paths.mapped_dir)
    if mapping_hash(users)!=dataset["user_mapping_hash"] or mapping_hash(items)!=dataset["mapping_hash"]:
        raise ValueError("mapping mismatch")
    root=paths.experiments_dir/"sparse_ranking_replay"; root.mkdir(parents=True,exist_ok=True)
    staging=root/("_staging_"+uuid.uuid4().hex)
    save_experiment(staging,config=dict(source=str(args.source.resolve()),source_hashes=hashes,policies=list(POLICIES),
        primary_pool="seed_2",secondary_pool="seed_4 exploratory correlated diagnostic",
        interpretation="recorded prefix priorities only, NOT unobserved weighted model scores",
        candidate_pool="each source variant's unchanged eligible pool; never union with missing donor items",
        primary_comparisons=2,individual_confidence=.975,bootstrap_samples=args.bootstrap_samples,
        metadata="source fields only; no fetch or serving-latency benchmark",production_changed=False),
        metrics={},seed=args.seed,dataset_info=dataset,runtime_seconds=0,write_readme=False)
    metrics=_compare(args.source/"records.jsonl",items,args.seed,args.bootstrap_samples,staging/"replays.jsonl")
    # Confirm every saved baseline aggregate against the original source metrics.
    original=json.loads((args.source/"metrics.json").read_text())
    for n,policies in metrics["comparison"].items():
        for metric,value in policies["baseline"]["metrics"].items():
            if not np.isclose(value,original["variants"][n]["metrics"][metric],atol=1e-13,rtol=0):
                raise ValueError("baseline reproduction mismatch")
    for name,h in hashes.items():
        if file_hash(args.source/name)!=h: raise ValueError("source changed during replay")
    metrics["runtime_seconds"]=time.perf_counter()-started
    manifest=yaml.safe_load((staging/"config.yaml").read_text(encoding="utf-8"))
    manifest["run"]["runtime_seconds"]=round(metrics["runtime_seconds"],2)
    (staging/"config.yaml").write_text(yaml.safe_dump(manifest,sort_keys=False,allow_unicode=True),encoding="utf-8")
    metrics["qualification"]="exploratory on inspected validation; untouched confirmation and real fetch/latency still required"
    (staging/"metrics.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    manifests={name:file_hash(staging/name) for name in ("config.yaml","metrics.json","replays.jsonl")}
    (staging/"artifact_hashes.json").write_text(json.dumps(manifests,indent=2),encoding="utf-8")
    output=next_experiment_dir(root); staging.rename(output)
    print("Saved ranking replay:",output,flush=True)
    for n,policies in metrics["comparison"].items():
        for p,r in policies.items(): print(n,p,json.dumps(r),flush=True)


if __name__=="__main__": main()
