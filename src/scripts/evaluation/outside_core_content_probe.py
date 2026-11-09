"""Validation-only diagnostic of history-title BM25 on outside-core targets."""
import argparse
from collections import Counter, defaultdict
import json
import sqlite3
import time

import numpy as np
import pandas as pd

from package.config import get_data_paths, load_config
from package.evaluation.recommender.experiment.next_experiment_dir import next_experiment_dir
from package.evaluation.recommender.experiment.save_experiment import save_experiment
from package.recommenders import build_interaction_matrix
from package.recommenders.shared import file_hash
from package.recommenders.shared import mapping_hash
from package.evaluation.recommender.analysis.outside_core_content_retriever import OutsideCoreContentRetriever


def _json_scalar(value):
    if isinstance(value,np.generic):
        return value.item()
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", action="append")
    ap.add_argument("--per-segment", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20261104)
    ap.add_argument("--candidate-budget", type=int, default=100)
    ap.add_argument("--timeout-seconds", type=float, default=2)
    args = ap.parse_args()
    if args.per_segment < 1 or args.candidate_budget < 20 or args.timeout_seconds <= 0:
        ap.error("positive sample size and budget >=20 required")
    paths = get_data_paths(domains=args.domain)
    started = time.perf_counter()
    print("[load] train/validation only", flush=True)
    stage = json.loads((paths.splits_dir / "stage_3.manifest.json").read_text())
    if stage["flags"].get("data_protocol") != "temporal_train_core":
        raise ValueError("temporal_train_core required")
    items = json.loads((paths.mapped_dir / "item2id.json").read_text())
    core_items = json.loads((paths.mapped_dir / "fit_core" / "item2id.json").read_text())
    id2item = {v:k for k,v in items.items()}
    shape = (stage["counts"]["num_users"], len(items))
    core_mask = np.zeros(shape[1], dtype=bool)
    core_mask[[items[key] for key in core_items]] = True
    train = pd.read_parquet(paths.split_path("train"), columns=["user_idx", "item_idx", "timestamp"])
    valid = pd.read_parquet(paths.split_path("validation"), columns=["user_idx", "item_idx", "timestamp"])
    cutoff = int(valid.timestamp.min())
    if train.timestamp.max() >= cutoff:
        raise ValueError("temporal boundary violation")
    history = build_interaction_matrix(train, *shape)
    full_targets = build_interaction_matrix(valid, *shape)
    outside = valid.loc[~core_mask[valid.item_idx.to_numpy()]]
    targets = build_interaction_matrix(outside, *shape)
    population = np.flatnonzero(np.diff(targets.indptr))
    sizes = np.diff(history.indptr)
    sparse_max = int(load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"])
    groups = {"cold": population[sizes[population] == 0],
              "sparse": population[(sizes[population] > 0) & (sizes[population] <= sparse_max)],
              "warm": population[sizes[population] > sparse_max]}
    rng = np.random.default_rng(args.seed)
    sampled = {s:sorted(rng.choice(pool, min(args.per_segment,len(pool)), replace=False).tolist()) for s,pool in groups.items()}
    selected = [u for group in sampled.values() for u in group]
    recent = train[train.user_idx.isin(selected)].sort_values("timestamp").groupby("user_idx").tail(3)
    seeds = recent.groupby("user_idx").item_idx.apply(list).to_dict()
    counts = np.asarray(history.sum(axis=0)).ravel()
    popular_order = np.argsort(-counts, kind="stable")
    del train, valid, outside
    sidecar = json.loads(paths.corpus_path.with_suffix(".meta.json").read_text())
    corpus_hash = file_hash(paths.corpus_path)
    if sidecar.get("artifact_sha256") != corpus_hash or sidecar.get("mapping_hash") != mapping_hash(items):
        raise ValueError("corpus checksum/mapping mismatch")
    print("[catalog] build TEMP FTS with visible outside-core items only", flush=True)
    conn = sqlite3.connect(paths.corpus_path.resolve().as_uri()+"?mode=ro", uri=True)
    conn.execute("PRAGMA temp_store=FILE")
    retriever = OutsideCoreContentRetriever(conn, core_items, cutoff, timeout_seconds=args.timeout_seconds)
    print(f"[catalog] {retriever.visible_items:,} visible items outside core", flush=True)
    directory = next_experiment_dir(paths.experiments_dir / "outside_core_content")
    directory.mkdir(parents=True)
    aggregates = defaultdict(Counter)
    statuses = Counter()
    with (directory/"records.jsonl").open("w",encoding="utf-8") as stream:
        for segment, cohort in sampled.items():
            for position, user in enumerate(cohort,1):
                a,b = history.indptr[user:user+2]
                seen = set(history.indices[a:b])
                a,b = targets.indptr[user:user+2]
                truth = set(targets.indices[a:b])
                all_truth = set(full_targets[user].indices)
                content = retriever.retrieve([id2item[i] for i in seeds.get(user,[])], limit=args.candidate_budget,
                                             excluded_ids=[id2item[i] for i in seen])
                statuses[content["status"]] += 1
                candidate_ids = [items[key] for key in content["candidates"]]
                # All history, not just the three query seeds, is excluded.
                candidate_ids = [i for i in candidate_ids if i not in seen]
                popular=[]
                for item in popular_order:
                    if item not in seen:
                        popular.append(int(item))
                        if len(popular)==args.candidate_budget:
                            break
                fused_scores = Counter()
                for order in (popular,candidate_ids):
                    for rank,item in enumerate(order,1):
                        fused_scores[item]+=1/(60+rank)
                fused=sorted(fused_scores,key=lambda i:(-fused_scores[i],i))
                methods={"history_popularity":popular,"outside_core_bm25":candidate_ids,"rrf60_popularity_content":fused}
                metrics={}
                for name,ranked in methods.items():
                    row={}
                    for k in (10,20,args.candidate_budget):
                        hits=sum(i in truth for i in ranked[:k])
                        row[f"outside_core_recall@{k}"]=hits/len(truth)
                        row[f"outside_core_hit_rate@{k}"]=float(hits>0)
                        row[f"all_target_recall@{k}"]=sum(i in all_truth for i in ranked[:k])/len(all_truth)
                    metrics[name]=row
                    for bucket in ("all",segment):
                        acc=aggregates[bucket+":"+name]
                        acc["users"]+=1
                        acc.update(row)
                stream.write(json.dumps({"user_idx":user,"segment":segment,"history_seeds":seeds.get(user,[]),
                    "outside_core_targets":sorted(truth),"targets_seen_by_user":len(truth&seen),
                    "targets_unobserved_in_train":sum(counts[i]==0 for i in truth),
                    "content":content,"ranked_indices":{n:r[:20] for n,r in methods.items()},"metrics":metrics},default=_json_scalar)+'\n')
                stream.flush()
                if position==1 or position%10==0 or position==len(cohort):
                    print(f"[probe:{segment}] {position}/{len(cohort)} elapsed={time.perf_counter()-started:.0f}s statuses={dict(statuses)}",flush=True)
    summary={key:{"users":acc["users"],"metrics":{k:v/acc["users"] for k,v in acc.items() if k!="users"}} for key,acc in aggregates.items()}
    conn.close()
    # save_experiment creates the result directory; keep progressively written rows.
    records=directory/"records.jsonl"
    record_hash=file_hash(records)
    save_experiment(directory/"summary",
        config={"parameters":vars(args),"sampled_user_ids":sampled,"candidate_budget":args.candidate_budget,
            "cohort":"diagnostic target-bearing users with outside-core validation targets; label-derived cohort, history-only query",
            "population_by_segment":{s:len(p) for s,p in groups.items()},
            "metadata_policy":"first_seen<=validation_start; TEMP FTS statistics from visible outside-core catalog only; static title/store/taxonomy proxy",
            "visible_outside_core_items":retriever.visible_items,"cutoff":cutoff,"statuses":dict(statuses),
            "lexical_order":"FTS5 rank Top-K shortlist; score/item_id tie sort inside the returned shortlist",
            "records_path":str(records),"records_sha256":record_hash,"corpus_sha256":corpus_hash,
            "input_hashes":{s:file_hash(paths.split_path(s)) for s in ("train","validation")}},
        metrics=summary,seed=args.seed,dataset_info={"tag":paths.tag,"eval_on":"validation"},
        runtime_seconds=time.perf_counter()-started,
        notes="Diagnostic pilot only. Cold users have no history query and stay in denominators. Errors/no-query count as empty content output. No target metadata in queries. No test rows read. RRF60 constants fixed before evaluation.")
    print(f"saved records -> {directory}; summary -> {directory/'summary'}",flush=True)


if __name__=="__main__":
    main()
