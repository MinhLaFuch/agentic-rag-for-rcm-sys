"""Fixed-candidate ranking evaluation for the deterministic recommendation tools.

The script builds candidate lists once from popularity, ItemCF, and history-title
search, saves them, then evaluates each scorer against those same lists.  It also
executes the deterministic retrieve -> rank -> metadata-fetch chain and records
quality, filtering loss, ties, and latency by user-history segment.

Run from ``src`` with ``PYTHONPATH=. python scripts/evaluation/ranking_eval.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from package.config import get_data_paths, get_domains, load_config
from package.data import ITEM_ID_SEPARATOR
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.tools import ItemCFTool, QueryTool, RecoModelTool, SemanticSearchTool
from package.tools.base import ToolCallLogger
from package.tools.corpus import build_corpus, load_corpus
from package.tools.evaluation import next_experiment_dir, save_experiment, segment_users_by_history, select_fit_target
from package.tools.evaluation.metrics import ranking_metrics_at_k
from package.tools.recommenders import ItemKNNRecommender, build_interaction_matrix
from package.tools.recommenders.item_knn_data_hash import item_knn_data_hash
from package.tools.score import BaselineScorer
from package.utils import ensure_utf8_stdout

from scripts.evaluation.candidate_recall import drop_seen, item_text_tables, round_robin, sample_users

SEGMENTS = ("cold", "sparse", "warm")
MERGES = ("union_rr", "union_all")


def _ids_to_namespaced(ids: list[int], id2item: dict[int, str]) -> list[str]:
    return [id2item[int(i)] for i in ids if int(i) in id2item]


def _summarize(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "mean": None, "p50": None, "p95": None}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
    }


def _ranking_metrics(
    ranked: list[list[int]],
    targets: list[set[int]],
    ks: list[int],
    catalog_size: int,
) -> dict[str, Any]:
    if not ranked:
        return {"users": 0, "catalog_coverage": {str(k): None for k in ks}}
    n_rel = np.asarray([len(t) for t in targets], dtype=np.int64)
    result: dict[str, Any] = {"users": len(ranked), "metrics": {}, "catalog_coverage": {}}
    for k in ks:
        hits = np.zeros((len(ranked), k), dtype=np.float64)
        returned: set[int] = set()
        for row, (pred, relevant) in enumerate(zip(ranked, targets)):
            top = pred[:k]
            returned.update(top)
            for pos, item in enumerate(top):
                hits[row, pos] = float(item in relevant)
        metrics = ranking_metrics_at_k(hits, n_rel, k)
        result["metrics"][str(k)] = {name: float(vals.mean()) for name, vals in metrics.items()}
        result["catalog_coverage"][str(k)] = len(returned) / catalog_size if catalog_size else 0.0
    return result


def _tie_stats(scores: np.ndarray, k: int) -> dict[str, float]:
    if scores.size < 2:
        return {"tie_pair_rate": 0.0, "top_k_boundary_tie": 0.0}
    unique_count = np.unique(scores).size
    pair_count = scores.size * (scores.size - 1) / 2
    tie_pairs = sum(int(n * (n - 1) / 2) for n in np.unique(scores, return_counts=True)[1])
    ordered = np.sort(scores)[::-1]
    boundary = float(k < len(ordered) and ordered[k - 1] == ordered[k])
    return {"tie_pair_rate": tie_pairs / pair_count, "top_k_boundary_tie": boundary}


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag")
    ap.add_argument("--eval-on", choices=("validation", "test"), default="validation")
    ap.add_argument("--per-segment", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--candidate-budget", type=int, default=100)
    ap.add_argument("--seed-items", type=int, default=5)
    ap.add_argument("--query-items", type=int, default=3)
    ap.add_argument("--neighbors", type=int, default=None)
    ap.add_argument("--ks", default="5,10,20")
    ap.add_argument("--popularity-weights", default="0,1e-6,1e-4,1e-3,1e-2")
    ap.add_argument("--allow-missing-corpus-sources", action="store_true")
    ap.add_argument("--no-prebuilt-corpus", action="store_true")
    ap.add_argument("--experiments-dir", type=Path)
    args = ap.parse_args()

    if args.per_segment < 1 or args.candidate_budget < 1:
        ap.error("--per-segment and --candidate-budget must be positive")
    ks = sorted({int(x) for x in args.ks.split(",") if x.strip()})
    weights = [float(x) for x in args.popularity_weights.split(",") if x.strip()]
    if not ks or min(ks) < 1 or max(ks) > args.candidate_budget * 3:
        ap.error("--ks must contain positive cutoffs no greater than 3*candidate-budget")
    if not weights or any(not np.isfinite(w) or w < 0 for w in weights):
        ap.error("--popularity-weights must be finite and non-negative")
    if len(set(weights)) != len(weights):
        ap.error("--popularity-weights must be unique")

    paths = get_data_paths(args.tag)
    domains = get_domains()
    meta_files = [(d, str(paths.meta_path(d))) for d in domains]
    t_start = time.perf_counter()

    train, validation, test = load_splits(paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, target_df = select_fit_target(train, validation, test, args.eval_on)
    user2id, item2id = load_mappings(paths.mapped_dir)
    id2user = {v: k for k, v in user2id.items()}
    id2item = {v: k for k, v in item2id.items()}
    num_users, num_items = len(user2id), len(item2id)
    namespaced = any(ITEM_ID_SEPARATOR in item for item in list(item2id)[:1000])

    fit_matrix = build_interaction_matrix(fit_df, num_users, num_items)
    target_by_user = target_df.groupby("user_idx")["item_idx"].apply(set).to_dict()
    history_sizes = np.diff(fit_matrix.indptr)
    sparse_max = int(load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"])
    segments_by_user = segment_users_by_history(list(target_by_user), history_sizes, sparse_max)
    sampled = sample_users(segments_by_user, args.per_segment, np.random.default_rng(args.seed))
    users = {u for group in sampled.values() for u in group}
    sampled_fit = fit_df[fit_df["user_idx"].isin(users)]
    sampled_fit = sampled_fit.sort_values("timestamp")
    recent = sampled_fit.groupby("user_idx")["item_idx"].apply(lambda s: list(s)[::-1]).to_dict()
    seen_of = {u: set(recent.get(u, [])) for u in users}

    if paths.corpus_path.exists() and not args.no_prebuilt_corpus:
        corpus, coverage = load_corpus(
            paths.corpus_path, meta_files, item2id,
            float(load_config("agent/agent_eval")["agent_eval"]["min_metadata_coverage"]),
            allow_missing_sources=args.allow_missing_corpus_sources,
        )
    else:
        corpus, _, coverage = build_corpus(
            meta_files, item2id,
            float(load_config("agent/agent_eval")["agent_eval"]["min_metadata_coverage"]),
        )

    neighbors = args.neighbors or int(load_config("eval/baselines")["baselines"]["item_knn"]["k"])
    knn_started = time.perf_counter()
    knn = ItemKNNRecommender(neighbors=neighbors).fit(fit_df[["user_idx", "item_idx"]])
    knn_seconds = time.perf_counter() - knn_started
    knn_hash = item_knn_data_hash(fit_df[["user_idx", "item_idx"]])
    item_cf = ItemCFTool(knn, item2id, corpus=corpus, logger=ToolCallLogger())
    semantic = SemanticSearchTool(corpus, logger=ToolCallLogger())
    query_tool = QueryTool(corpus, logger=ToolCallLogger())
    get_text = item_text_tables(corpus, namespaced)
    popular_order = np.argsort(-np.asarray(fit_matrix.sum(axis=0)).ravel(), kind="stable")
    max_candidates = int(load_config("agent/tools")["tools"]["max_candidates"])

    candidate_records: list[dict[str, Any]] = []
    retrieval_times: dict[str, dict[str, list[float]]] = {
        segment: defaultdict(list) for segment in SEGMENTS
    }
    retrieval_lists: dict[tuple[int, str], list[int]] = {}
    target_sets: dict[int, set[int]] = {}
    novel_targets: dict[int, set[int]] = {}
    for segment in SEGMENTS:
        for user in sampled[segment]:
            seen = seen_of[user]
            ask = min(args.candidate_budget + len(seen), max_candidates)
            target_sets[user] = set(target_by_user[user])
            novel_targets[user] = target_sets[user] - seen
            popularity = [int(i) for i in popular_order[:ask]]

            recent_ids = recent.get(user, [])
            seed_names = _ids_to_namespaced(recent_ids[: args.seed_items], id2item)
            start = time.perf_counter()
            cf_result = item_cf(items=seed_names, top_k=ask) if seed_names else None
            retrieval_times[segment]["item_cf"].append(time.perf_counter() - start)
            cf_ids = [item2id[c["item_id"]] for c in cf_result.data["candidates"] if c["item_id"] in item2id] if cf_result and cf_result.ok else []

            query_names = _ids_to_namespaced(recent_ids[: args.query_items], id2item)
            text_info = get_text(query_names)
            query = " ".join(text_info[item][0] for item in query_names if item in text_info)
            start = time.perf_counter()
            sem_result = semantic(query=query, limit=ask) if query.strip() else None
            retrieval_times[segment]["semantic"].append(time.perf_counter() - start)
            sem_ids = []
            if sem_result and sem_result.ok:
                for row in sem_result.data["candidates"]:
                    item_name = row["item_id"] if namespaced else row["original_item_id"]
                    if item_name in item2id:
                        sem_ids.append(item2id[item_name])

            raw_sources = {"popularity": popularity, "item_cf": cf_ids, "semantic": sem_ids}
            filtered_sources = {name: drop_seen(items, seen, args.candidate_budget) for name, items in raw_sources.items()}
            union_rr = round_robin(list(filtered_sources.values()), args.candidate_budget)
            union_all = list(dict.fromkeys(i for name in raw_sources for i in filtered_sources[name]))
            raw_union = list(dict.fromkeys(i for name in raw_sources for i in raw_sources[name]))
            raw_union_after_seen = [i for i in raw_union if i not in seen]
            seen_filtered_union = list(dict.fromkeys(i for name in filtered_sources for i in filtered_sources[name]))
            retrieval_lists[(user, "union_rr")] = union_rr
            retrieval_lists[(user, "union_all")] = union_all
            candidate_records.append({
                "user_idx": int(user), "user_id": id2user[user], "segment": segment,
                "targets": sorted(target_sets[user]), "targets_seen_in_fit": sorted(target_sets[user] & seen),
                "targets_unseen_in_fit": sorted(novel_targets[user]),
                "seen_count": len(seen),
                "sources_raw": {name: _ids_to_namespaced(ids, id2item) for name, ids in raw_sources.items()},
                "sources_after_seen_filter": {name: _ids_to_namespaced(ids, id2item) for name, ids in filtered_sources.items()},
                "raw_union": _ids_to_namespaced(raw_union, id2item),
                "raw_union_after_seen": _ids_to_namespaced(raw_union_after_seen, id2item),
                "seen_filtered_union": _ids_to_namespaced(seen_filtered_union, id2item),
                "candidate_sets": {"union_rr": _ids_to_namespaced(union_rr, id2item), "union_all": _ids_to_namespaced(union_all, id2item)},
                "source_failures": {
                    "item_cf": cf_result.error if cf_result and not cf_result.ok else None,
                    "semantic": sem_result.error if sem_result and not sem_result.ok else None,
                },
            })
            item_cf.logger.records.clear()
            semantic.logger.records.clear()

    # The lists and targets are frozen before any ranking variant is evaluated.
    candidate_records_by_user = {row["user_idx"]: row for row in candidate_records}
    ranking_results: dict[str, Any] = {}
    all_scored: list[dict[str, Any]] = []
    for merge in MERGES:
        ranking_results[merge] = {}
        for weight in weights:
            variant = "baseline" if np.isclose(weight, 1e-6, rtol=0, atol=1e-15) else f"popularity_weight_{weight:g}"
            scorer = BaselineScorer(knn, popularity_weight=weight)
            reco = RecoModelTool(scorer, user2id, item2id, corpus=corpus)
            ranked_by_segment: dict[str, list[list[int]]] = {s: [] for s in SEGMENTS}
            relevant_by_segment: dict[str, list[set[int]]] = {s: [] for s in SEGMENTS}
            ranking_latency: dict[str, list[float]] = defaultdict(list)
            fetch_latency: dict[str, list[float]] = defaultdict(list)
            ties: dict[str, dict[str, list[float]]] = {s: defaultdict(list) for s in SEGMENTS}
            loss: dict[str, dict[str, list[int]]] = {s: defaultdict(list) for s in SEGMENTS}
            fetch_success: dict[str, list[float]] = defaultdict(list)
            rows_for_variant = []

            for record in candidate_records:
                user, segment = record["user_idx"], record["segment"]
                candidates = retrieval_lists[(user, merge)]
                user_id = record["user_id"]
                start = time.perf_counter()
                # Rank the complete fixed candidate list so tie rate and the max-K boundary tie
                # include the candidates immediately below the recommendation cutoff.
                output = reco.execute(
                    user_id=user_id, candidates=_ids_to_namespaced(candidates, id2item),
                    top_k=len(candidates), exclude_seen=True,
                )
                elapsed = time.perf_counter() - start
                ranking_latency[segment].append(elapsed)
                ranked_ids = [item2id[r["item_id"]] for r in output["ranked"] if r["item_id"] in item2id]
                seen_removed = len(output["excluded_seen"])
                unscored_removed = len(output["unscored_item_ids"])
                loss[segment]["candidate_input"].append(len(candidates))
                loss[segment]["seen_removed"].append(seen_removed)
                loss[segment]["unscored_removed"].append(unscored_removed)
                loss[segment]["ranked_returned"].append(len(ranked_ids))
                # Per-user retrieval filtering loss is measured on unique raw candidates before per-source budget cuts.
                retrieval_record = candidate_records_by_user[user]
                loss[segment]["retrieval_raw_union"].append(len(retrieval_record["raw_union"]))
                loss[segment]["retrieval_seen_dropped"].append(
                    len(retrieval_record["raw_union"]) - len(retrieval_record["raw_union_after_seen"])
                )

                if novel_targets[user]:
                    ranked_by_segment[segment].append(ranked_ids)
                    relevant_by_segment[segment].append(novel_targets[user])

                rank_scores = np.asarray([r["score"] for r in output["ranked"]], dtype=np.float64)
                tie = _tie_stats(rank_scores, max(ks))
                ties[segment]["tie_pair_rate"].append(tie["tie_pair_rate"])
                ties[segment]["top_k_boundary_tie"].append(tie["top_k_boundary_tie"])

                top_ranked = output["ranked"][: max(ks)]
                start = time.perf_counter()
                fetched = query_tool.execute(item_ids=[r["item_id"] for r in top_ranked]) if top_ranked else {"items": []}
                fetch_latency[segment].append(time.perf_counter() - start)
                fetch_success[segment].append(float(len(fetched.get("items", [])) == len(top_ranked)))

                row = {
                    "request_id": f"{merge}:{user}", "user_idx": user, "segment": segment,
                    "merge": merge, "scorer": variant, "popularity_weight": weight,
                    "targets": sorted(target_sets[user]), "targets_unseen_in_fit": sorted(novel_targets[user]),
                    "candidate_ids": _ids_to_namespaced(candidates, id2item),
                    "ranked_ids": [r["item_id"] for r in output["ranked"]],
                    "scores": [r["score"] for r in output["ranked"]],
                    "excluded_seen": output["excluded_seen"], "unscored_item_ids": output["unscored_item_ids"],
                    "ranking_latency_seconds": elapsed,
                    "fetch_latency_seconds": fetch_latency[segment][-1],
                    "fetch_success": bool(fetch_success[segment][-1]),
                    "recommendations_at_max_k": [r["item_id"] for r in top_ranked],
                    **tie,
                }
                rows_for_variant.append(row)
                all_scored.append(row)

            per_segment = {}
            for segment in SEGMENTS:
                metric = _ranking_metrics(ranked_by_segment[segment], relevant_by_segment[segment], ks, num_items)
                l = loss[segment]
                c_in = int(sum(l["candidate_input"]))
                c_seen = int(sum(l["seen_removed"]))
                c_unscored = int(sum(l["unscored_removed"]))
                metric.update({
                    "sampled_users": len(sampled[segment]),
                    "users_with_unseen_targets": len(relevant_by_segment[segment]),
                    "users_without_unseen_targets": len(sampled[segment]) - len(relevant_by_segment[segment]),
                    "target_items_seen_in_fit": int(sum(len(target_sets[u] - novel_targets[u]) for u in sampled[segment])),
                    "target_items_unseen_in_fit": int(sum(len(novel_targets[u]) for u in sampled[segment])),
                    "filtering": {
                        "retrieval_raw_union_candidates": int(sum(l["retrieval_raw_union"])),
                        "retrieval_seen_dropped": int(sum(l["retrieval_seen_dropped"])),
                        "input_candidates": c_in,
                        "removed_seen": c_seen,
                        "removed_unscored": c_unscored,
                        "returned_ranked": int(sum(l["ranked_returned"])),
                        "retrieval_seen_loss_rate": sum(l["retrieval_seen_dropped"]) / sum(l["retrieval_raw_union"]) if sum(l["retrieval_raw_union"]) else 0.0,
                        "unscored_loss_rate": c_unscored / c_in if c_in else 0.0,
                        "total_loss_rate_after_merge": (c_seen + c_unscored) / c_in if c_in else 0.0,
                    },
                    "ranking_latency_seconds": _summarize(ranking_latency[segment]),
                    "metadata_fetch_latency_seconds": _summarize(fetch_latency[segment]),
                    "metadata_fetch_success_rate": float(np.mean(fetch_success[segment])) if fetch_success[segment] else None,
                    "ties": {key: float(np.mean(vals)) if vals else None for key, vals in ties[segment].items()},
                })
                per_segment[segment] = metric
            ranking_results[merge][variant] = {
                "popularity_weight": weight,
                "per_segment": per_segment,
                "rows": rows_for_variant,
            }

    # Retrieval metrics use the same held-out sample and the same seen-item filtering as candidate_recall.py.
    retrieval_summary = {}
    for merge in MERGES:
        retrieval_summary[merge] = {}
        for segment in SEGMENTS:
            us = sampled[segment]
            cand = [retrieval_lists[(u, merge)] for u in us]
            targets = [target_sets[u] for u in us]
            novel = [novel_targets[u] for u in us]
            from package.tools.evaluation import candidate_retrieval_metrics
            retrieval_summary[merge][segment] = {
                "all_validation_targets": candidate_retrieval_metrics(cand, targets, num_items),
                "unseen_validation_targets": candidate_retrieval_metrics(cand, novel, num_items),
                "mean_target_seen_in_fit": float(np.mean([len(target_sets[u] - novel_targets[u]) / max(1, len(target_sets[u])) for u in us])) if us else None,
                "candidate_generation_latency_seconds": {
                    name: _summarize(retrieval_times[segment][name])
                    for name in ("item_cf", "semantic")
                },
            }

    exp_root = args.experiments_dir or (paths.experiments_dir / "ranking_eval")
    exp_dir = next_experiment_dir(exp_root)
    max_sampled_user = max(users) if users else 0
    metadata = {
        "tag": paths.tag, "splits_dir": str(paths.splits_dir), "eval_on": args.eval_on,
        "num_users": num_users, "num_items": num_items,
        "mapping_hash": hashlib.sha256("".join(sorted(item2id)).encode()).hexdigest(),
        "split_files": {
            name: {"path": str(paths.split_path(name)), "size_bytes": paths.split_path(name).stat().st_size,
                   "mtime_ns": paths.split_path(name).stat().st_mtime_ns}
            for name in ("train", "validation", "test")
        },
    }
    config = {
        "seed": args.seed, "per_segment": args.per_segment, "sampled_user_ids": sampled,
        "candidate_budget_per_source": args.candidate_budget, "candidate_merges": list(MERGES),
        "retrieval": {"sources": ["popularity", "item_cf", "semantic"], "seed_items": args.seed_items,
                      "query_items": args.query_items, "semantic_query_mode": "titles_from_fit_history",
                      "item_knn_neighbors": neighbors, "item_knn_fit_data_hash": knn_hash,
                      "item_knn_fit_seconds": knn_seconds},
        "scorers": {"type": "BaselineScorer", "popularity_weights": weights,
                    "baseline_weight": 1e-6, "same_saved_candidate_lists": True},
        "ks": ks,
        "target_protocol": "validation interactions; ranking quality reported on targets not in fit history; all-target candidate recall also retained",
        "corpus": {"path": str(paths.corpus_path) if paths.corpus_path.exists() and not args.no_prebuilt_corpus else None,
                   "metadata_coverage": coverage,
                   "missing_sources": [p for _, p in meta_files if not Path(p).exists()],
                   "allow_missing_sources": args.allow_missing_corpus_sources,
                   "mode": "in_memory_build" if args.no_prebuilt_corpus or not paths.corpus_path.exists() else "prebuilt"},
        "max_sampled_user_idx": max_sampled_user,
    }
    metrics = {
        "k_values": ks,
        "catalog_size": num_items,
        "retrieval": retrieval_summary,
        "ranking": {merge: {variant: {"popularity_weight": v["popularity_weight"], "per_segment": v["per_segment"]}
                             for variant, v in variants.items()} for merge, variants in ranking_results.items()},
        "runtime_seconds": time.perf_counter() - t_start,
    }
    save_experiment(exp_dir, config=config, metrics=metrics, seed=args.seed,
                    dataset_info=metadata, runtime_seconds=time.perf_counter() - t_start,
                    notes=("All scorer variants receive identical persisted candidates per user and merge. "
                           "Candidate generation uses popularity, ItemCF, and titles from fit history (realistic offline proxy). "
                           "Ranking metrics use validation targets not seen in fit; target items already in fit are reported separately. "
                           "This deterministic chain does not invoke the LLM planner."))
    with (exp_dir / "candidate_lists.jsonl").open("w", encoding="utf-8") as f:
        for row in candidate_records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (exp_dir / "scored.jsonl").open("w", encoding="utf-8") as f:
        for row in all_scored:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Saved ranking evaluation: {exp_dir}")
    for merge, variants in metrics["ranking"].items():
        for variant, data in variants.items():
            seg_text = " | ".join(
                f"{seg}:n={data['per_segment'][seg]['users']},NDCG@10={data['per_segment'][seg]['metrics'].get('10',{}).get('ndcg@10',0):.4f},Recall@10={data['per_segment'][seg]['metrics'].get('10',{}).get('recall@10',0):.4f}"
                for seg in SEGMENTS
            )
            print(f"{merge} {variant} {seg_text}")


if __name__ == "__main__":
    main()
