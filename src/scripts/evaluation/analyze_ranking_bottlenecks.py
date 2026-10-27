"""Read saved candidates/scores: retrieval loss, ranking headroom and source fusion.

No fitting, corpus loading, LLM calls or production changes. Oracle quantities
use targets only for diagnostics. Replay policies use source order only, with
exactly the baseline candidate pool. Results are exploratory validation results.
"""
from __future__ import annotations

import argparse
from array import array
from collections import Counter, defaultdict
from contextlib import closing, ExitStack
import json
from pathlib import Path
import time

import numpy as np
import yaml

from package.config import get_data_paths
from package.data.mapping import load_mappings
from package.tools.evaluation import next_experiment_dir, save_experiment
from package.tools.evaluation.metrics import ranking_metrics_at_k
from package.tools.evaluation.stage_progress import StageProgress
from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash

SOURCES = ("popularity", "item_cf", "semantic")
POLICIES = ("baseline", "popularity_first", "semantic_first", "cf_first", "rrf_60")


def _score_rows(path, merge):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["merge"] == merge and row["scorer"] == "baseline":
                yield row


def _replay_order(pool, sources, policy):
    """No target, user label or held-out metadata enters this ordering."""
    allowed = set(pool)
    if policy == "rrf_60":
        scores = dict.fromkeys(pool, 0.)
        for names in sources.values():
            for rank, item in enumerate(dict.fromkeys(names), 1):
                if item in allowed:
                    scores[item] += 1. / (60. + rank)
        return sorted(pool, key=lambda i: -scores[i])  # stable input-order ties
    priority = {"semantic_first": ("semantic", "item_cf", "popularity"),
                "cf_first": ("item_cf", "semantic", "popularity"),
                "popularity_first": ("popularity", "item_cf", "semantic")}[policy]
    return list(dict.fromkeys([i for source in priority for i in sources[source] if i in allowed] + pool))


def _metrics(names, targets, item2id, k):
    hits = np.zeros((1,k))
    for rank, name in enumerate(names[:k]):
        hits[0,rank] = item2id[name] in targets
    return {name:float(v[0]) for name,v in ranking_metrics_at_k(hits, np.array([len(targets)]), k).items()}


def _paired(delta, rng, samples):
    d = np.asarray(delta, dtype=np.float64)
    if not len(d):
        return {"users":0,"mean_delta":None,"ci95":None}
    values, counts = np.unique(d, return_counts=True)
    estimates = rng.multinomial(len(d),counts/len(d),size=samples) @ values / len(d)
    return {"users":len(d),"mean_delta":float(d.mean()),"ci95":np.percentile(estimates,[2.5,97.5]).tolist(),
            "improved":int((d>0).sum()),"worse":int((d<0).sum()),"unchanged":int((d==0).sum())}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--experiment", type=Path, required=True)
    ap.add_argument("--selection-pilot", type=Path, required=True)
    ap.add_argument("--output-root",type=Path)
    ap.add_argument("--seed",type=int,default=42)
    ap.add_argument("--bootstrap-samples",type=int,default=5000)
    args = ap.parse_args()
    if args.bootstrap_samples < 1:
        ap.error("bootstrap-samples must be positive")
    started = time.perf_counter()
    config = yaml.safe_load((args.experiment/"config.yaml").read_text(encoding="utf-8"))
    original = json.loads((args.experiment/"metrics.json").read_text())
    if config["run"]["dataset"]["eval_on"] != "validation":
        raise ValueError("exploratory policy comparisons must use validation")
    pilot = yaml.safe_load((args.selection_pilot/"config.yaml").read_text(encoding="utf-8"))
    pilot_users = {u for group in pilot["config"]["sampled_user_ids"].values() for u in group}
    paths = get_data_paths(config["run"]["dataset"]["tag"])
    user2id, item2id = load_mappings(paths.mapped_dir)
    if mapping_hash(item2id) != config["run"]["dataset"]["mapping_hash"] or mapping_hash(user2id) != config["run"]["dataset"]["user_mapping_hash"]:
        raise ValueError("current mapping does not match experiment")
    del user2id
    source_hashes = {name:file_hash(args.experiment/name) for name in ("config.yaml","metrics.json","candidate_lists.jsonl","scored.jsonl")}
    published = json.loads((args.experiment/"artifact_hashes.json").read_text())
    if any(source_hashes[n] != h for n,h in published.items()):
        raise ValueError("source artifact checksum mismatch")
    ks = config["config"]["ks"]
    merges = config["config"]["candidate_merges"]
    totals, quality, source_quality, delta = {}, {}, {}, {}
    counts = defaultdict(Counter)
    support = defaultdict(Counter)
    progress = StageProgress("offline diagnostic",sum(map(len,config["config"]["sampled_user_ids"].values())),every=1000)
    seen_users = set()
    with ExitStack() as stack:
        streams = {merge:stack.enter_context(closing(_score_rows(args.experiment/"scored.jsonl",merge))) for merge in merges}
        with (args.experiment/"candidate_lists.jsonl").open(encoding="utf-8") as candidates:
            for number,line in enumerate(candidates,1):
                row = json.loads(line)
                u, seg = row["user_idx"],row["segment"]
                if u in seen_users:
                    raise ValueError("duplicate candidate user")
                seen_users.add(u)
                targets = set(row["targets_unseen_in_fit"])
                scores = {merge:next(streams[merge]) for merge in merges}
                for merge,base in scores.items():
                    if base["user_idx"] != u or base["candidate_ids"] != row["candidate_sets"][merge] or set(base["targets_unseen_in_fit"]) != targets:
                        raise ValueError("candidate/scored alignment mismatch")
                if not targets:
                    counts[seg]["no_novel_ground_truth"] += 1
                    progress.update(number)
                    continue
                counts[seg]["eligible_users"] += 1
                for source,names in row["sources_after_seen_filter"].items():
                    values = _metrics(names,targets,item2id,10)
                    state = source_quality.setdefault((seg,source),Counter())
                    state.update(values)
                    state["pool_hit_rate"] += bool(set(item2id[i] for i in names) & targets)
                for merge,base in scores.items():
                    pool = row["candidate_sets"][merge]
                    available = set(item2id[i] for i in pool) & targets
                    state = totals.setdefault((merge,seg),Counter())
                    state["users"] += 1
                    state["targets"] += len(targets)
                    state["retrieved_targets"] += len(available)
                    state["retrieved_recall_sum"] += len(available)/len(targets)
                    state["users_with_retrieved_target"] += bool(available)
                    membership = {s:set(item2id[i] for i in names) for s,names in row["sources_after_seen_filter"].items()}
                    for item in available:
                        signature = "+".join(s for s in SOURCES if item in membership[s])
                        support[merge,seg][signature] += 1
                    baseline = _metrics(base["ranked_ids"],targets,item2id,10)
                    oracle_recall = min(10,len(available))/len(targets)
                    state["oracle_recall10_sum"] += oracle_recall
                    state["retrieval_loss_sum"] += 1-len(available)/len(targets)
                    state["capacity_loss_sum"] += (len(available)-min(10,len(available)))/len(targets)
                    state["ranking_loss_sum"] += oracle_recall-baseline["recall@10"]
                    state["actual_recall10_sum"] += baseline["recall@10"]
                    state["actual_hit10_users"] += baseline["hit_rate@10"]
                    for policy in POLICIES:
                        ranked = base["ranked_ids"] if policy=="baseline" else _replay_order(pool,row["sources_after_seen_filter"],policy)
                        if policy != "baseline" and set(ranked) != set(pool):
                            raise ValueError("replay changed candidate pool")
                        q = quality.setdefault((merge,seg,policy),Counter())
                        for k in ks:
                            q.update(_metrics(ranked,targets,item2id,k))
                        diff = _metrics(ranked,targets,item2id,10)["ndcg@10"]-baseline["ndcg@10"]
                        for scope in ("all", "new_only" if u not in pilot_users else "pilot_only"):
                            delta.setdefault((merge,seg,policy,scope),array("d")).append(diff)
                progress.update(number)
        for stream in streams.values():
            if next(stream,None) is not None:
                raise ValueError("extra baseline scored records")
    rng = np.random.default_rng(args.seed)
    result = {"segments":dict(counts),"bottlenecks":{},"source_standalone_at10":{},"fixed_pool_replays":{}}
    for (seg,source),q in source_quality.items():
        n=counts[seg]["eligible_users"]
        result["source_standalone_at10"].setdefault(seg,{})[source] = {k:v/n for k,v in q.items()}
    for (merge,seg),s in totals.items():
        n=s["users"]
        b = {"users":n,"target_pairs":s["targets"],"retrieved_target_pairs":s["retrieved_targets"],
             "catalog_retrieval_recall_macro":s["retrieved_recall_sum"]/n,
             "oracle_recall_at10_fixed_pool":s["oracle_recall10_sum"]/n,
             "actual_recall_at10":s["actual_recall10_sum"]/n,
             "recall_loss_decomposition":{"retrieval":s["retrieval_loss_sum"]/n,"top10_capacity":s["capacity_loss_sum"]/n,"ranking":s["ranking_loss_sum"]/n},
             "users_with_retrieved_target":s["users_with_retrieved_target"],"actual_hit10_users":s["actual_hit10_users"],
             "target_source_support":dict(support[merge,seg])}
        if abs(sum(b["recall_loss_decomposition"].values())+b["actual_recall_at10"]-1)>1e-12:
            raise ValueError("recall loss decomposition inconsistent")
        result["bottlenecks"].setdefault(merge,{})[seg] = b
        policies = result["fixed_pool_replays"].setdefault(merge,{}).setdefault(seg,{})
        for policy in POLICIES:
            policies[policy] = {"metrics":{k:v/n for k,v in quality[merge,seg,policy].items()},
                "paired_ndcg10":{scope:_paired(delta.get((merge,seg,policy,scope),[]),rng,args.bootstrap_samples) for scope in ("all","new_only","pilot_only")}}
        policies["rrf_60"]["paired_ndcg10_vs_popularity_first"] = {
            scope:_paired(np.asarray(delta.get((merge,seg,"rrf_60",scope),[]))-
                          np.asarray(delta.get((merge,seg,"popularity_first",scope),[])),rng,args.bootstrap_samples)
            for scope in ("all","new_only","pilot_only")}
        for k,values in original["ranking"][merge]["baseline"]["per_segment"][seg]["metrics"].items():
            for name,value in values.items():
                if not np.isclose(policies["baseline"]["metrics"][name],value,atol=1e-13,rtol=0):
                    raise ValueError("baseline metric recomputation mismatch")
    if len(seen_users) != sum(map(len,config["config"]["sampled_user_ids"].values())):
        raise ValueError("candidate sample count mismatch")
    output = save_experiment(next_experiment_dir(args.output_root or paths.experiments_dir/"ranking_diagnostics"),
        config={"source_experiment":str(args.experiment.resolve()),"source_sha256":source_hashes,
                "selection_pilot":str(args.selection_pilot.resolve()),"selection_pilot_config_sha256":file_hash(args.selection_pilot/"config.yaml"),
                "protocol":config["config"]["protocol"],"policies":list(POLICIES),"rrf_offset":60,"ks":ks,
                "bootstrap_samples":args.bootstrap_samples,"paired_bootstrap":"percentile within segment; exploratory, no multiplicity correction",
                "oracle_scope":"diagnostic only; uses labels; never deployable",
                "candidate_pool":"fixed to each baseline merge; no target info in replay policies",
                "latency_scope":"offline analysis runtime only; no measured production latency for replay policies"},
        metrics=result,seed=args.seed,dataset_info=config["run"]["dataset"],runtime_seconds=time.perf_counter()-started,
        notes="Saved-artifact bottleneck diagnosis; no training, retrieval, LLM or production changes. Replays are exploratory validation policies, not confirmed tuned production scorers.")
    print(f"Saved diagnostic: {output}",flush=True)
    for merge,segments in result["bottlenecks"].items():
        for seg,b in segments.items():
            print(merge,seg,b,flush=True)
            print("NDCG@10",{p:v["metrics"]["ndcg@10"] for p,v in result["fixed_pool_replays"][merge][seg].items()},flush=True)


if __name__ == "__main__":
    main()
