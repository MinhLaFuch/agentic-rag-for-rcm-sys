"""
Candidate recall: do the retrieval tools put the held-out items in front of the reranker?

For each sampled validation (or test) user we ask every candidate source for N items, drop the
items the user already has in the fit data, and check how many of the user's held-out items
appear.  Nothing here uses an LLM; it answers "is retrieval the bottleneck?" before any
reranking or agent work.

Sources
  popularity   global top-N by train count               (works for everyone, incl. cold)
  item_cf      SimilarTool seeded with the user's recent items   (needs history)
  semantic     SearchTool, query built as below         (needs a query)
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
    PYTHONPATH=. python scripts/evaluation/candidate_recall.py --domain Video_Games
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
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data import ITEM_ID_SEPARATOR, build_first_seen_timestamps, namespaced_item_id
from package.data.manifest import verify_tag_manifest
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.tools import SimilarTool, SearchTool
from package.tools import get_tool_limits
from package.tools.base import ToolCallLogger
from package.corpus import build_corpus, load_corpus
from package.evaluation.recommender.metrics.retrieval import (
    candidate_retrieval_metrics,
    item_familiarity_metrics,
)
from package.evaluation.recommender.utils import latency_summary, sha256_file
from package.evaluation.recommender.experiment import next_experiment_dir, save_experiment
from package.evaluation.recommender.config import segment_users_by_history, select_fit_target
from package.recommenders import build_interaction_matrix
from package.recommenders import ItemKNNRecommender
from package.recommenders.shared import item_knn_data_hash
from package.utils import ensure_utf8_stdout
from package.corpus.apply_metadata_policy import apply_metadata_policy
from package.evaluation.recommender.core.evaluation_protocol import evaluation_protocol
from package.evaluation.recommender.analysis.cohort_policy_for_paths import cohort_policy_for_paths
from package.evaluation.recommender.analysis.build_core_model import build_core_model
from package.evaluation.recommender.utils.normalize_query_text import normalize_query_text
from package.recommenders.shared import mapping_hash

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


def merge_candidate_unions(lists: dict[str, list[int]], n: int, *, hybrid: bool):
    """Keep the baseline union fixed; replace BM25 with hybrid in the ablation."""
    merged, latencies = {}, {}
    variants = {"union": ("popularity", "item_cf", "semantic")}
    if hybrid:
        variants["union_hybrid"] = ("popularity", "item_cf", "hybrid")
    for prefix, sources in variants.items():
        rankings = [lists[source] for source in sources if source in lists]
        started = time.perf_counter()
        merged[prefix + "_rr"] = round_robin(rankings, n)
        latencies[prefix + "_rr"] = time.perf_counter() - started
        started = time.perf_counter()
        merged[prefix + "_all"] = list(dict.fromkeys(item for ranking in rankings for item in ranking))
        latencies[prefix + "_all"] = time.perf_counter() - started
    return merged, latencies


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
    ap.add_argument("--domain", action="append",
                    help="Domain của bundle dữ liệu + meta để nạp (lặp lại). "
                         "Mặc định: tất cả -> bundle 'multi_domain'; 1 domain -> bundle tên domain; "
                         "tập con khác bị từ chối.")
    ap.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    ap.add_argument("--per-segment", type=int, default=None,
                    help="Override số user lấy mẫu mỗi segment")
    ap.add_argument("--query-mode", action="append", choices=["history", "category_oracle"], default=None,
                    help="Chế độ truy vấn (lặp lại được, vd --query-mode history --query-mode category_oracle)")
    ap.add_argument("--metadata-policy", choices=["historical_static_catalog", "snapshot", "no_filter"], default=None)
    ap.add_argument("--retrieval", choices=["bm25", "hybrid"], default="bm25")
    ap.add_argument("--allow-missing-corpus-sources", action="store_true")
    ap.add_argument("--tag", help="Explicit existing bundle; does not bypass manifest validation")
    ap.add_argument("--embeddings-path", type=Path, help="Explicit full artifact directory or legacy NPZ")
    args = ap.parse_args()

    # Mọi tham số đọc từ configs/eval/candidate_recall.yaml, eval/baselines.yaml, eval/segment_thresholds.yaml
    cfg = load_config("eval/candidate_recall")["candidate_recall"]
    baselines = load_config("eval/baselines")["baselines"]
    budgets = sorted(int(b) for b in cfg["budgets"])
    if not budgets or any(n <= 0 for n in budgets) or len(set(budgets)) != len(budgets):
        raise SystemExit("candidate_recall.budgets must be unique positive integers")
    if max(budgets) > MAX_CANDIDATES:
        raise SystemExit(f"largest candidate budget cannot exceed tools.max_candidates={MAX_CANDIDATES}")
    per_segment = int(args.per_segment) if args.per_segment is not None else int(cfg["per_segment"])
    seed_items = int(cfg["seed_items"])
    query_items = int(cfg["query_items"])
    neighbors = int(baselines["item_knn"]["k"])
    seed = int(baselines["seed"])
    query_modes = [str(mode) for mode in args.query_mode] if args.query_mode else [str(mode) for mode in cfg["query_modes"]]
    allowed_query_modes = {"history", "category_oracle"}
    if not query_modes or set(query_modes) - allowed_query_modes:
        raise SystemExit(f"candidate_recall.query_modes must contain values from {sorted(allowed_query_modes)}")
    if seed_items <= 0 or query_items <= 0 or neighbors <= 0 or per_segment <= 0:
        raise SystemExit("seed_items, query_items, neighbors, per_segment must be positive")
    metadata_policy_name = args.metadata_policy or str(cfg["metadata_policy"])
    query_normalization = str(cfg["query_normalization"])
    use_prebuilt = bool(cfg["use_prebuilt_corpus"])
    allow_missing = args.allow_missing_corpus_sources or bool(cfg["allow_missing_corpus_sources"])

    data_paths = resolve_bundle_paths(tag=args.tag, domains=args.domain)
    tag_manifest = verify_tag_manifest(data_paths, domains=args.domain or get_domains())
    if tag_manifest["warnings"]:
        print(f"Manifest warnings: {tag_manifest['warnings']}", flush=True)
    if metadata_policy_name == "no_filter":
        print("LEGACY DIAGNOSTIC: no temporal catalog filtering; not comparable to historical evaluation.", flush=True)
    experiments_dir = data_paths.output_dir("candidate_recall")
    meta_files = [(d, str(data_paths.meta_path(d))) for d in (args.domain or get_domains())]

    n_max = max(budgets)
    sparse_max = load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"]
    rng = np.random.default_rng(seed)
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
    sampled = sample_users(seg_of, per_segment, rng)
    sampled_users = {user for users in sampled.values() for user in users}
    # Build histories only for sampled evaluation users, not for the entire multi-million-user fit set.
    sampled_fit = fit_df[fit_df["user_idx"].isin(sampled_users)]
    fit_sorted = sampled_fit.sort_values("timestamp") if "timestamp" in sampled_fit.columns else sampled_fit
    recent = fit_sorted.groupby("user_idx")["item_idx"].apply(lambda s: list(s)[::-1]).to_dict()
    seen_of = {u: set(recent.get(u, [])) for u in sampled_users}

    # ---- corpus + tools
    print("Load/build corpus")
    corpus_started = time.perf_counter()
    if data_paths.corpus_path.exists() and use_prebuilt:
        corpus, coverage = load_corpus(
            data_paths.corpus_path,
            meta_files,
            item2id,
            float(cfg["min_metadata_coverage"]),
            allow_missing_sources=allow_missing,
        )
    else:
        if not use_prebuilt:
            print("  Bypassing cached corpus; building from configured metadata in memory")
        first_seen_ts = build_first_seen_timestamps([(d, data_paths.cleaned_path(d)) for d, _ in meta_files])
        corpus, _, coverage = build_corpus(meta_files, item2id, float(cfg["min_metadata_coverage"]), first_seen_ts=first_seen_ts)
    corpus_load_seconds = time.perf_counter() - corpus_started
    item_text = item_text_tables(corpus, namespaced)
    print(f"  metadata covers {coverage:.1%} of mapped items")

    metadata_policy = apply_metadata_policy(corpus, metadata_policy_name, as_of_timestamp=int(target_df.timestamp.min()))
    protocol_manifest = evaluation_protocol(eval_on=args.eval_on, tag=data_paths.tag, fit_df=fit_df,
        target_df=target_df, user2id=user2id, item2id=item2id, segments=seg_of,
        sampled=sampled, metadata_policy=metadata_policy, evaluation_kind="candidate",
        cohort_policy=cohort_policy_for_paths(data_paths))

    protocol_manifest["query_normalization"] = query_normalization

    embedding_provenance = None
    vector_store = query_encoder = None
    if args.retrieval == "hybrid":
        from scripts.data_pipeline.build_item_embeddings import load_validated_embeddings
        from package.embeddings import TextEncoder
        npz_path = args.embeddings_path or data_paths.corpus_dir / f"item_embeddings_{data_paths.tag}.npz"
        vector_store, encoder_impl, embedding_provenance = load_validated_embeddings(
            npz_path, data_paths.corpus_path,
        )
        query_encoder = TextEncoder(encoder_impl.encode, dimension=vector_store.dimension)
        print(f"Hybrid ready: {len(vector_store):,} vectors, provider={embedding_provenance['provider']}")

    cached_knn_path = data_paths.item_knn_path(args.eval_on)
    knn_started = time.perf_counter()
    knn_status = "fit_fresh_cache_ignored"
    fit_pairs = fit_df[["user_idx", "item_idx"]]
    knn_fit_data_hash = None
    knn_cache_data_hash = None
    cache_meta_path = cached_knn_path.with_suffix(".meta.json")
    if cache_meta_path.exists():
        knn_cache_data_hash = json.loads(cache_meta_path.read_text(encoding="utf-8")).get("data_hash")
    knn = build_core_model(data_paths, args.eval_on, neighbors, fit_df, user2id, item2id)
    if knn is not None:
        knn_status = knn._evaluation_artifact_status
        knn_fit_data_hash = knn._fit_data_hash
        protocol_manifest["item_knn"] = knn._evaluation_fit_provenance
        protocol_manifest["cf_history"] = "all pre-target history; similarity and popularity frozen on train_core"
        print(f"ItemKNN: {knn_status}", flush=True)
    else:
        print("Fit ItemKNN on current fit split (legacy bundle)", flush=True)
        knn_fit_data_hash = item_knn_data_hash(fit_pairs)
        knn = ItemKNNRecommender(neighbors=neighbors).fit(fit_pairs)
    knn_seconds = time.perf_counter() - knn_started
    item_cf = SimilarTool(knn, item2id, corpus=corpus, logger=ToolCallLogger())
    search_bm25 = SearchTool(corpus, logger=ToolCallLogger())

    search_hybrid = None
    if vector_store is not None and query_encoder is not None:
        search_hybrid = SearchTool(
            corpus,
            logger=ToolCallLogger(),
            vector_store=vector_store,
            query_encoder=query_encoder,
            rrf_k=60,
        )
    has_hybrid = search_hybrid is not None
    active_sources = ("popularity", "item_cf", "semantic", "hybrid", "union_rr", "union_all", "union_hybrid_rr", "union_hybrid_all") if has_hybrid else ("popularity", "item_cf", "semantic", "union_rr", "union_all")
    popularity = knn.scores if hasattr(knn, "_evaluation_fit_provenance") else np.asarray(fit_matrix.sum(axis=0)).ravel()
    pop_order = np.argsort(-popularity, kind="stable").tolist()
    fit_item_seen = np.asarray(fit_matrix.sum(axis=0)).ravel() > 0

    def cand_key(c: dict) -> str:  # semantic candidates carry both id forms
        return c["item_id"] if namespaced else c["original_item_id"]

    def ask_limit(u: int) -> int:  # room for the items we will drop as already-seen
        return min(n_max + len(seen_of[u]), MAX_CANDIDATES)

    def get_item_cf(u: int) -> list[int] | None:
        seeds = [id2item[i] for i in recent.get(u, [])[: seed_items]]
        if not seeds:
            return None
        res = item_cf(items=seeds, top_k=ask_limit(u))
        item_cf.logger.records.clear()
        return [item2id[c["item_id"]] for c in res.data.get("candidates", [])] if res.ok else []

    def get_semantic(u: int, mode: str) -> list[int] | None:
        if mode == "history":
            query_ids = [id2item[i] for i in recent.get(u, [])[: query_items]]
        else:  # category_oracle
            query_ids = [id2item[i] for i in target_by_user[u]]
        text_by_id = item_text(query_ids)
        column = 0 if mode == "history" else 1
        query = " ".join(text_by_id[item_id][column] for item_id in query_ids if item_id in text_by_id)
        query = normalize_query_text(query, query_normalization)
        if not query.strip():
            return None
        res = search_bm25(query=query, limit=ask_limit(u))
        search_bm25.logger.records.clear()
        if not res.ok:
            return []
        return [item2id[k] for k in map(cand_key, res.data["candidates"]) if k in item2id]

    def get_hybrid(u: int, mode: str) -> list[int] | None:
        if search_hybrid is None:
            return None
        if mode == "history":
            query_ids = [id2item[i] for i in recent.get(u, [])[: query_items]]
        else:  # category_oracle
            query_ids = [id2item[i] for i in target_by_user[u]]
        text_by_id = item_text(query_ids)
        column = 0 if mode == "history" else 1
        query = " ".join(text_by_id[item_id][column] for item_id in query_ids if item_id in text_by_id)
        query = normalize_query_text(query, query_normalization)
        if not query.strip():
            return None
        res = search_hybrid(query=query, limit=ask_limit(u))
        search_hybrid.logger.records.clear()
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
            predictions = {s: {n: [] for n in budgets} for s in active_sources}
            target_sets: list[set[int]] = []
            base_latency_sources = ("popularity", "item_cf", "semantic", "hybrid") if has_hybrid else ("popularity", "item_cf", "semantic")
            source_latencies = {s: [] for s in base_latency_sources}
            merge_latencies = {s: {n: [] for n in budgets} for s in (("union_rr", "union_all", "union_hybrid_rr", "union_hybrid_all") if has_hybrid else ("union_rr", "union_all"))}
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
                if has_hybrid:
                    started = time.perf_counter()
                    hybrid_candidates = get_hybrid(u, mode)
                    source_latencies["hybrid"].append(time.perf_counter() - started)
                    ranked["hybrid"] = hybrid_candidates

                if ranked["item_cf"] is None and ranked["semantic"] is None and (not has_hybrid or ranked.get("hybrid") is None):
                    no_query += 1
                for n in budgets:
                    lists = {s: drop_seen(r, seen, n) for s, r in ranked.items() if r is not None}
                    unions, merge_times = merge_candidate_unions(lists, n, hybrid=has_hybrid)
                    lists.update(unions)
                    for source, elapsed in merge_times.items():
                        merge_latencies[source][n].append(elapsed)
                    if n == budgets[-1]:
                        size_union.append(len(lists["union_all"]))
                    for s in active_sources:
                        predictions[s][n].append(lists.get(s, []))  # no input counts as no retrieved candidates
                # Clear logger records after each user to prevent unbounded growth
                item_cf.logger.records.clear()
                search_bm25.logger.records.clear()
                if search_hybrid is not None:
                    search_hybrid.logger.records.clear()
            reach = np.mean([fit_item_seen[list(target_by_user[u])].mean() for u in users]) if users else float("nan")
            source_metrics = {
                source: {
                    str(n): candidate_retrieval_metrics(predictions[source][n], target_sets, num_items)
                    for n in budgets
                }
                for source in active_sources
            }
            item_metrics = {
                source: {
                    str(n): item_familiarity_metrics(predictions[source][n], target_sets, fit_item_seen)
                    for n in budgets
                }
                for source in active_sources
            }
            latency_metrics = {source: latency_summary(values) for source, values in source_latencies.items()}
            latency_metrics.update({
                source: {str(n): latency_summary(merge_latencies[source][n]) for n in budgets}
                for source in merge_latencies
            })
            metrics[mode][seg] = {
                "users": len(users),
                "users_without_any_query_or_history": no_query,
                "target_items_seen_in_fit": float(reach),  # compatibility alias: catalog warm, NOT same-user repeat
                "target_catalog_warm_fraction_macro_user": float(reach),
                "target_same_user_repeat_fraction_macro_user": float(np.mean([len(target_by_user[u] & seen_of[u]) / len(target_by_user[u]) for u in users])) if users else None,
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
                    for source in active_sources
                },
            }
            m = metrics[mode][seg]
            print(f"[{seg}] users={m['users']} no_input={no_query} targets_seen_in_fit={reach:.2f} union_all_size~{m['mean_union_all_size']:.0f}")
            for s in active_sources:
                print("   " + s.ljust(11) + "  ".join(
                    f"recall@{n}={m['candidate_metrics'][s][str(n)]['recall'] or 0:.3f} "
                    f"hit@{n}={m['candidate_metrics'][s][str(n)]['hit_rate'] or 0:.3f} "
                    f"size={m['candidate_metrics'][s][str(n)]['mean_candidate_set_size'] or 0:.1f}"
                    for n in budgets
                ))

    metadata_source_records = {
        domain: {
            "path": path,
            "exists": Path(path).exists(),
            "size_bytes": Path(path).stat().st_size if Path(path).exists() else None,
            "sha256": sha256_file(path) if Path(path).exists() else None,
        }
        for domain, path in meta_files
    }
    exp_dir = save_experiment(
        next_experiment_dir(experiments_dir),
        config={"retrieval": args.retrieval, "embedding_provenance": embedding_provenance,
                "audit_profile": tag_manifest.get("audit_profile"),
                "union_sources": {"baseline": ["popularity", "item_cf", "semantic"], "hybrid": ["popularity", "item_cf", "hybrid"] if has_hybrid else []},
                "manifest_status": tag_manifest["status"], "manifest_sha256": tag_manifest["manifest_sha256"],
                "protocol": protocol_manifest, "budgets": budgets, "per_segment": per_segment, "seed_items": seed_items,
                "query_items": query_items, "neighbors": neighbors, "query_modes": query_modes,
                "evaluation_protocol": {mode: ("oracle_upper_bound" if mode == "category_oracle" else "realistic_offline_proxy") for mode in query_modes},
                "sampled_user_ids": sampled, "sparse_max": sparse_max,
                "knn_artifact_status": knn_status, "knn_fit_seconds": round(knn_seconds, 6),
                "knn_fit_data_hash": knn_fit_data_hash, "knn_cache_data_hash": knn_cache_data_hash,
                "knn_cache_used": knn_status == "validated_train_core_cache",
                "corpus_load_seconds": round(corpus_load_seconds, 6),
                "corpus_source_validation": {
                    "mode": "built_from_metadata_in_memory" if not use_prebuilt else "loaded_prebuilt",
                    "metadata_sources": metadata_source_records,
                    "allow_missing_sources": allow_missing,
                    "missing_sources": [path for _, path in meta_files if not Path(path).exists()],
                },
                "corpus_artifacts": {
                    "sqlite_path": None if not use_prebuilt else str(data_paths.corpus_path),
                    "sqlite_sha256": sha256_file(data_paths.corpus_path) if data_paths.corpus_path.exists() and use_prebuilt else None,
                    "manifest_path": str(data_paths.corpus_path.with_suffix(".meta.json")),
                    "manifest_sha256": sha256_file(data_paths.corpus_path.with_suffix(".meta.json")) if data_paths.corpus_path.with_suffix(".meta.json").exists() and use_prebuilt else None,
                    "source_hash_semantics": getattr(corpus, "_source_provenance", {"source_hash_protocol": "built_from_current_sources"}),
                }},
        metrics=metrics,
        seed=seed,
        dataset_info={"tag": data_paths.tag, "splits_dir": str(data_paths.splits_dir), "eval_on": args.eval_on, "num_users": num_users,
                      "num_items": num_items, "id_format": "namespaced" if namespaced else "plain",
                      "metadata_coverage": round(coverage, 4),
                      "mapping_hash": mapping_hash(item2id), "user_mapping_hash": mapping_hash(user2id),
                      "mapping_hash_protocol": "sorted_key_index_json_v1",
                      "split_files": {name: {"path": str(data_paths.split_path(name)),
                                             "size_bytes": data_paths.split_path(name).stat().st_size,
                                             "mtime_ns": data_paths.split_path(name).stat().st_mtime_ns, "sha256": sha256_file(data_paths.split_path(name))}
                                      for name in ("train", "validation", "test")}},
        runtime_seconds=time.time() - t_start,
        notes="history is a realistic offline proxy (titles from fit history), not a real query log. category_oracle is an upper bound using held-out metadata and must not be reported as realistic performance. Candidate coverage is micro Recall over held-out user-item pairs; catalog coverage is unique returned catalog items divided by catalog size.",
    )
    print(f"\nsaved -> {exp_dir}")


if __name__ == "__main__":
    main()
