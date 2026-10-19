"""
Candidate recall: do the retrieval tools put the held-out items in front of the reranker?

For each sampled validation (or test) user we ask every candidate source for N items, drop the
items the user already has in the fit data, and check how many of the user's held-out items
appear.  Nothing here uses an LLM; it answers "is retrieval the bottleneck?" before any
reranking or agent work.

Sources
  popularity   global top-N by train count               (works for everyone, incl. cold)
  item_cf      ItemCFTool seeded with the user's recent items   (needs history)
  semantic     SemanticSearchTool, query built as below         (needs a query)
  union        all three, merged round-robin to N (budget-matched) and plain union (larger)

Where the semantic query comes from (there are no real user queries offline, so it is simulated):
  history          titles of the user's last few fit items.       Honest, but empty for cold users.
  category_oracle  categories of the user's held-out items.       Simulates "I want a <category>";
                   an UPPER BOUND that leaks target information - never report it as a result.

Segments follow the evaluator: cold = 0 fit interactions, sparse = 1..sparse_max, warm = more.
By default only ``history`` queries are evaluated; ``category_oracle`` must be requested explicitly and is labeled
as a target-informed upper bound. Metrics include candidate-set size, coverage, catalog reach, latency, and item familiarity.

Reads splits/mappings from resource/ (see data_paths.yaml) and meta_<Domain>.jsonl.gz from resource/raw/.
Defaults for budgets, sample sizes, etc. live in configs/eval/candidate_recall.yaml → candidate_recall.

    PYTHONPATH=. python scripts/evaluation/candidate_recall.py --eval-on validation
    PYTHONPATH=. python scripts/evaluation/candidate_recall.py --eval-on validation --query-modes category_oracle
    PYTHONPATH=. python scripts/evaluation/candidate_recall.py --tag vg_toys --domain Video_Games --domain Toys_and_Games
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from itertools import islice
from pathlib import Path

import numpy as np
import pandas as pd

from package.config import get_data_paths, get_domains, load_config
from package.data import ITEM_ID_SEPARATOR, namespaced_item_id
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.tools import ItemCFTool, SemanticSearchTool
from package.tools import get_tool_limits
from package.tools.base import ToolCallLogger
from package.tools.corpus import build_corpus, load_corpus
from package.tools.evaluation import (
    candidate_retrieval_metrics,
    item_familiarity_metrics,
    latency_summary,
    next_experiment_dir,
    save_experiment,
    segment_users_by_history,
    select_fit_target,
)
from package.tools.recommenders import build_interaction_matrix
from package.tools.recommenders import ItemKNNRecommender
from package.tools.recommenders.item_knn_data_hash import item_knn_data_hash
from package.tools.recommenders.load_item_knn import load_item_knn
from package.utils import ensure_utf8_stdout

MAX_CANDIDATES = get_tool_limits().max_candidates

SEGMENTS = ("cold", "sparse", "warm")
SOURCES = ("popularity", "item_cf", "semantic", "union_rr", "union_all")


# ----------------------------------------------------------------------------- data


def item_text_tables(corpus, namespaced: bool):
    """Return a lazy lookup for title/category text stored in the corpus."""
    cache: dict[str, tuple[str, str]] = {}

    def get(item_ids: list[str]) -> dict[str, tuple[str, str]]:
        missing = list(dict.fromkeys(item_id for item_id in item_ids if item_id not in cache))
        if missing:
            domains = corpus.domains()
            db_ids = missing if namespaced else [namespaced_item_id(domain, item_id) for item_id in missing for domain in domains]
            marks = ",".join("?" for _ in db_ids)
            rows, _ = corpus.select(
                "SELECT i.item_id, i.original_item_id, i.title, i.main_category, group_concat(c.category, ' ') AS categories "
                "FROM items i LEFT JOIN item_categories c USING(item_id) "
                f"WHERE i.item_id IN ({marks}) GROUP BY i.item_id",
                db_ids,
                max_rows=len(db_ids),
            )
            for row in rows:
                parts = [row.get("main_category"), row.get("categories")]
                key = row["item_id"] if namespaced else row["original_item_id"]
                cache[key] = (row.get("title") or "", " ".join(str(p) for p in parts if p))
        return {item_id: cache[item_id] for item_id in item_ids if item_id in cache}

    return get


# ----------------------------------------------------------------------------- helpers


def round_robin(lists: list[list[int]], n: int) -> list[int]:
    """Interleave ranked lists, skipping duplicates, until n items (budget-matched union)."""
    out, seen = [], set()
    for rank in range(max((len(l) for l in lists), default=0)):
        for l in lists:
            if rank < len(l) and l[rank] not in seen:
                seen.add(l[rank])
                out.append(l[rank])
                if len(out) == n:
                    return out
    return out


def drop_seen(ranked: list[int], seen: set[int], n: int) -> list[int]:
    return list(dict.fromkeys(i for i in ranked if i not in seen))[:n]


def sample_users(seg_of: dict[int, str], per_segment: int, rng: np.random.Generator) -> dict[str, list[int]]:
    if per_segment <= 0:
        raise ValueError("per_segment must be a positive integer")
    out = {}
    for seg in SEGMENTS:
        users = sorted(u for u, s in seg_of.items() if s == seg)
        rng.shuffle(users)
        out[seg] = users[:per_segment]
    return out


# ----------------------------------------------------------------------------- main


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", help="Tên lần chạy (mặc định: tag trong run_tag.yaml).")
    ap.add_argument("--domain", action="append", help="Domain có meta để nạp (lặp lại; mặc định: tất cả trong domains.yaml)")
    ap.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    ap.add_argument("--n", help="candidate budgets, comma separated (mặc định: candidate_recall.budgets)")
    ap.add_argument("--per-segment", type=int, help="max users sampled per segment")
    ap.add_argument("--seed-items", type=int, help="recent fit items used as ItemCF seeds")
    ap.add_argument("--query-items", type=int, help="recent fit items whose titles form the history query")
    ap.add_argument("--neighbors", type=int, help="ItemKNN k (mặc định: baselines.item_knn.k)")
    ap.add_argument("--seed", type=int, help="mặc định: baselines.seed")
    ap.add_argument(
        "--query-modes",
        default="history",
        help="Query source: history (default realistic offline proxy) and/or category_oracle (explicit oracle upper bound).",
    )
    ap.add_argument(
        "--allow-missing-corpus-sources",
        action="store_true",
        help="Load a prebuilt corpus when raw metadata files are unavailable; schema and item mapping are still validated.",
    )
    ap.add_argument("--experiments-dir", help="mặc định: <experiments_dir>/<candidate_recall.experiments_subdir>")
    args = ap.parse_args()

    # CLI > configs/eval/candidate_recall.yaml / eval/baselines.yaml / eval/segment_thresholds.yaml
    cfg = load_config("eval/candidate_recall")["candidate_recall"]
    baselines = load_config("eval/baselines")["baselines"]
    args.n = args.n or ",".join(str(b) for b in cfg["budgets"])
    args.per_segment = args.per_segment or cfg["per_segment"]
    args.seed_items = args.seed_items or cfg["seed_items"]
    args.query_items = args.query_items or cfg["query_items"]
    args.neighbors = args.neighbors or baselines["item_knn"]["k"]
    args.seed = baselines["seed"] if args.seed is None else args.seed
    budgets = sorted(int(x) for x in args.n.split(","))
    if not budgets or any(n <= 0 for n in budgets) or len(set(budgets)) != len(budgets):
        raise SystemExit("candidate budgets must be unique positive integers")
    if max(budgets) > MAX_CANDIDATES:
        raise SystemExit(f"largest candidate budget cannot exceed tools.max_candidates={MAX_CANDIDATES}")
    if args.seed_items <= 0 or args.query_items <= 0 or args.neighbors <= 0:
        raise SystemExit("seed-items, query-items, and neighbors must be positive")
    if args.per_segment <= 0:
        raise SystemExit("per-segment must be positive")
    query_modes = [mode.strip() for mode in args.query_modes.split(",") if mode.strip()]
    allowed_query_modes = {"history", "category_oracle"}
    if not query_modes or set(query_modes) - allowed_query_modes:
        raise SystemExit(f"--query-modes must contain values from {sorted(allowed_query_modes)}")

    data_paths = get_data_paths(args.tag)
    args.experiments_dir = args.experiments_dir or data_paths.experiments_dir / cfg["experiments_subdir"]
    args.splits_dir = str(data_paths.splits_dir)
    meta_files = [(d, str(data_paths.meta_path(d))) for d in (args.domain or get_domains())]

    n_max = max(budgets)
    sparse_max = load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"]
    rng = np.random.default_rng(args.seed)
    t_start = time.time()

    # ---- splits, mapping, fit/target (same protocol as run_baselines.py)
    train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, target_df = select_fit_target(train, val, test, args.eval_on)
    user2id, item2id = load_mappings(data_paths.mapped_dir)
    id2item = {v: k for k, v in item2id.items()}
    num_users, num_items = len(user2id), len(item2id)
    namespaced = any(ITEM_ID_SEPARATOR in k for k in islice(item2id, 1000))
    print(f"item ids in mapping are {'namespaced (Domain::asin)' if namespaced else 'plain parent_asin'}")

    fit_matrix = build_interaction_matrix(fit_df, num_users, num_items)
    target_by_user = target_df.groupby("user_idx")["item_idx"].apply(set).to_dict()
    hist_size = np.diff(fit_matrix.indptr)
    seg_of = segment_users_by_history(target_by_user, hist_size, sparse_max)
    sampled = sample_users(seg_of, args.per_segment, rng)
    sampled_users = {user for users in sampled.values() for user in users}
    # Build histories only for sampled evaluation users, not for the entire multi-million-user fit set.
    sampled_fit = fit_df[fit_df["user_idx"].isin(sampled_users)]
    fit_sorted = sampled_fit.sort_values("timestamp") if "timestamp" in sampled_fit.columns else sampled_fit
    recent = fit_sorted.groupby("user_idx")["item_idx"].apply(lambda s: list(s)[::-1]).to_dict()
    seen_of = {u: set(recent.get(u, [])) for u in sampled_users}

    # ---- corpus + tools
    print("Load/build corpus")
    corpus_started = time.perf_counter()
    if data_paths.corpus_path.exists():
        corpus, coverage = load_corpus(
            data_paths.corpus_path,
            meta_files,
            item2id,
            float(cfg["min_metadata_coverage"]),
            allow_missing_sources=args.allow_missing_corpus_sources,
        )
    else:
        corpus, _, coverage = build_corpus(meta_files, item2id, float(cfg["min_metadata_coverage"]))
    corpus_load_seconds = time.perf_counter() - corpus_started
    item_text = item_text_tables(corpus, namespaced)
    print(f"  metadata covers {coverage:.1%} of mapped items")

    cached_knn_path = data_paths.item_knn_path(args.eval_on)
    knn_started = time.perf_counter()
    knn_status = "fit_fresh"
    fit_pairs = fit_df[["user_idx", "item_idx"]]
    knn_fit_data_hash = None
    knn_cache_data_hash = None
    if args.neighbors == int(baselines["item_knn"]["k"]) and cached_knn_path.exists():
        print(f"Load ItemKNN from {cached_knn_path}")
        cache_meta_path = cached_knn_path.with_suffix(".meta.json")
        if cache_meta_path.exists():
            knn_cache_data_hash = json.loads(cache_meta_path.read_text(encoding="utf-8")).get("data_hash")
        try:
            knn = load_item_knn(cached_knn_path, args.neighbors, fit_pairs)
            knn_status = "cache_validated"
            knn_fit_data_hash = knn._fit_data_hash
        except ValueError as exc:
            if "Data hash mismatch" not in str(exc):
                raise
            print("  cached ItemKNN data hash differs from current fit split; fitting a fresh model")
            knn_fit_data_hash = getattr(exc, "current_data_hash", None)
            knn = ItemKNNRecommender(neighbors=args.neighbors).fit(fit_pairs)
            knn_status = "refit_after_data_hash_mismatch"
    else:
        print("Fit ItemKNN on fit data")
        knn = ItemKNNRecommender(neighbors=args.neighbors).fit(fit_pairs)
    if knn_fit_data_hash is None:
        knn_fit_data_hash = item_knn_data_hash(fit_pairs)
    knn_seconds = time.perf_counter() - knn_started
    item_cf = ItemCFTool(knn, item2id, logger=ToolCallLogger())
    search = SemanticSearchTool(corpus, logger=ToolCallLogger())
    pop_order = np.argsort(-np.asarray(fit_matrix.sum(axis=0)).ravel(), kind="stable").tolist()
    fit_item_seen = np.asarray(fit_matrix.sum(axis=0)).ravel() > 0

    def cand_key(c: dict) -> str:  # semantic candidates carry both id forms
        return c["item_id"] if namespaced else c["original_item_id"]

    def ask_limit(u: int) -> int:  # room for the items we will drop as already-seen
        return min(n_max + len(seen_of[u]), MAX_CANDIDATES)

    def get_item_cf(u: int) -> list[int] | None:
        seeds = [id2item[i] for i in recent.get(u, [])[: args.seed_items]]
        if not seeds:
            return None
        res = item_cf(items=seeds, top_k=ask_limit(u))
        item_cf.logger.records.clear()
        return [item2id[c["item_id"]] for c in res.data.get("candidates", [])] if res.ok else []

    def get_semantic(u: int, mode: str) -> list[int] | None:
        if mode == "history":
            query_ids = [id2item[i] for i in recent.get(u, [])[: args.query_items]]
        else:  # category_oracle
            query_ids = [id2item[i] for i in target_by_user[u]]
        text_by_id = item_text(query_ids)
        column = 0 if mode == "history" else 1
        query = " ".join(text_by_id[item_id][column] for item_id in query_ids if item_id in text_by_id)
        if not query.strip():
            return None
        res = search(query=query, limit=ask_limit(u))
        search.logger.records.clear()
        if not res.ok:
            return []
        return [item2id[k] for k in map(cand_key, res.data["candidates"]) if k in item2id]

    # ---- evaluate
    metrics: dict = {}
    for mode in query_modes:
        protocol = "oracle_upper_bound" if mode == "category_oracle" else "realistic_offline_proxy"
        print(f"\n=== query mode: {mode} ({protocol})")
        metrics[mode] = {}
        for seg in SEGMENTS:
            users = sampled[seg]
            predictions = {s: {n: [] for n in budgets} for s in SOURCES}
            target_sets: list[set[int]] = []
            source_latencies = {s: [] for s in ("popularity", "item_cf", "semantic")}
            merge_latencies = {s: {n: [] for n in budgets} for s in ("union_rr", "union_all")}
            size_union, no_query = [], 0
            for u in users:
                targets, seen = target_by_user[u], seen_of[u]
                target_sets.append(targets)
                started = time.perf_counter()
                popularity_candidates = pop_order[: ask_limit(u)]
                source_latencies["popularity"].append(time.perf_counter() - started)
                started = time.perf_counter()
                item_cf_candidates = get_item_cf(u)
                source_latencies["item_cf"].append(time.perf_counter() - started)
                started = time.perf_counter()
                semantic_candidates = get_semantic(u, mode)
                source_latencies["semantic"].append(time.perf_counter() - started)
                ranked = {
                    "popularity": popularity_candidates,
                    "item_cf": item_cf_candidates,
                    "semantic": semantic_candidates,
                }
                if ranked["item_cf"] is None and ranked["semantic"] is None:
                    no_query += 1
                for n in budgets:
                    lists = {s: drop_seen(r, seen, n) for s, r in ranked.items() if r is not None}
                    started = time.perf_counter()
                    lists["union_rr"] = round_robin(list(lists.values()), n)  # budget-matched: n items
                    merge_latencies["union_rr"][n].append(time.perf_counter() - started)
                    started = time.perf_counter()
                    lists["union_all"] = list(dict.fromkeys(i for s in ranked if s in lists for i in lists[s]))  # up to 3n
                    merge_latencies["union_all"][n].append(time.perf_counter() - started)
                    if n == budgets[-1]:
                        size_union.append(len(lists["union_all"]))
                    for s in SOURCES:
                        predictions[s][n].append(lists.get(s, []))  # no input counts as no retrieved candidates
                # Clear logger records after each user to prevent unbounded growth
                item_cf.logger.records.clear()
                search.logger.records.clear()
            reach = np.mean([fit_item_seen[list(target_by_user[u])].mean() for u in users]) if users else float("nan")
            source_metrics = {
                source: {
                    str(n): candidate_retrieval_metrics(predictions[source][n], target_sets, num_items)
                    for n in budgets
                }
                for source in SOURCES
            }
            item_metrics = {
                source: {
                    str(n): item_familiarity_metrics(predictions[source][n], target_sets, fit_item_seen)
                    for n in budgets
                }
                for source in SOURCES
            }
            latency_metrics = {source: latency_summary(values) for source, values in source_latencies.items()}
            latency_metrics.update({
                source: {str(n): latency_summary(merge_latencies[source][n]) for n in budgets}
                for source in merge_latencies
            })
            metrics[mode][seg] = {
                "users": len(users),
                "users_without_any_query_or_history": no_query,
                "target_items_seen_in_fit": float(reach),
                "mean_union_all_size": float(np.mean(size_union)) if size_union else 0.0,
                "candidate_metrics": source_metrics,
                "item_familiarity_metrics": item_metrics,
                "latency": latency_metrics,
                # Keep the original metric locations so existing comparison code can still read old experiments.
                **{
                    source: {
                        str(n): {
                            "recall": source_metrics[source][str(n)]["recall"],
                            "hit": source_metrics[source][str(n)]["hit_rate"],
                        }
                        for n in budgets
                    }
                    for source in SOURCES
                },
            }
            m = metrics[mode][seg]
            print(f"[{seg}] users={m['users']} no_input={no_query} targets_seen_in_fit={reach:.2f} union_all_size~{m['mean_union_all_size']:.0f}")
            for s in SOURCES:
                print("   " + s.ljust(11) + "  ".join(
                    f"recall@{n}={m['candidate_metrics'][s][str(n)]['recall'] or 0:.3f} "
                    f"hit@{n}={m['candidate_metrics'][s][str(n)]['hit_rate'] or 0:.3f} "
                    f"size={m['candidate_metrics'][s][str(n)]['mean_candidate_set_size'] or 0:.1f}"
                    for n in budgets
                ))

    exp_dir = save_experiment(
        next_experiment_dir(args.experiments_dir),
        config={"budgets": budgets, "per_segment": args.per_segment, "seed_items": args.seed_items,
                "query_items": args.query_items, "neighbors": args.neighbors, "query_modes": query_modes,
                "evaluation_protocol": {mode: ("oracle_upper_bound" if mode == "category_oracle" else "realistic_offline_proxy") for mode in query_modes},
                "sampled_user_ids": sampled, "sparse_max": sparse_max,
                "knn_artifact_status": knn_status, "knn_fit_seconds": round(knn_seconds, 6),
                "knn_fit_data_hash": knn_fit_data_hash, "knn_cache_data_hash": knn_cache_data_hash,
                "knn_cache_has_mapping_hash": False,
                "corpus_load_seconds": round(corpus_load_seconds, 6),
                "corpus_source_validation": {
                    "allow_missing_sources": bool(args.allow_missing_corpus_sources),
                    "missing_sources": [path for _, path in meta_files if not Path(path).exists()],
                }},
        metrics=metrics,
        seed=args.seed,
        dataset_info={"tag": data_paths.tag, "splits_dir": args.splits_dir, "eval_on": args.eval_on, "num_users": num_users,
                      "num_items": num_items, "id_format": "namespaced" if namespaced else "plain",
                      "metadata_coverage": round(coverage, 4),
                      "mapping_hash": hashlib.sha256("".join(sorted(item2id)).encode()).hexdigest(),
                      "split_files": {name: {"path": str(data_paths.split_path(name)),
                                             "size_bytes": data_paths.split_path(name).stat().st_size,
                                             "mtime_ns": data_paths.split_path(name).stat().st_mtime_ns}
                                      for name in ("train", "validation", "test")}},
        runtime_seconds=time.time() - t_start,
        notes="history is a realistic offline proxy (titles from fit history), not a real query log. category_oracle is an upper bound using held-out metadata and must not be reported as realistic performance. Candidate coverage is micro Recall over held-out user-item pairs; catalog coverage is unique returned catalog items divided by catalog size.",
    )
    print(f"\nsaved -> {exp_dir}")


if __name__ == "__main__":
    main()
