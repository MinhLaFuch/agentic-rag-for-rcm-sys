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
from datetime import datetime, timezone
import uuid
import yaml
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from package.config import get_data_paths, get_domains, load_config
from package.data import ITEM_ID_SEPARATOR, build_first_seen_timestamps
from package.data.manifest import verify_tag_manifest
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.tools import SimilarTool, LookupTool, RankTool, SearchTool
from package.tools.base import ToolCallLogger
from package.corpus import build_corpus, load_corpus
from package.evaluation.recommender.experiment import next_experiment_dir, save_experiment
from package.evaluation.recommender.config import segment_users_by_history, select_fit_target
from package.evaluation.recommender.metrics.ranking import ranking_metrics_at_k
from package.recommenders.runtime.item_knn_recommender import ItemKNNRecommender
from package.recommenders.shared.build_interaction_matrix import build_interaction_matrix
from package.recommenders.shared import item_knn_data_hash, mapping_hash, file_hash
from package.tools.scoring import BaselineScorer, HybridScorer, MultiSignalReranker
from package.tools.scoring.evidence_scorer import EvidenceScorer
from package.utils import ensure_utf8_stdout
from package.corpus.apply_metadata_policy import apply_metadata_policy
from package.evaluation.recommender.core.evaluation_protocol import evaluation_protocol
from package.evaluation.recommender.analysis.build_core_model import build_core_model
from package.evaluation.recommender.analysis.confirmation_cohort import confirmation_cohort
from package.evaluation.recommender.analysis.cohort_policy_for_paths import cohort_policy_for_paths
from package.evaluation.recommender.utils.normalize_query_text import normalize_query_text

from scripts.evaluation.candidate_recall import drop_seen, item_text_tables, round_robin, sample_users

SEGMENTS = ("cold", "sparse", "warm")
MERGES = ("union_rr", "union_all")
MATRIX_REQUIRED_FILES = ("config.json", "candidate_sets.jsonl", "frozen.json", "artifact_hashes.json")
RANKING_REQUIRED_FILES = ("config.yaml", "metrics.json", "candidate_lists.jsonl", "scored.jsonl")


def _frozen_source_kind(source: Path) -> str:
    if (source / "frozen.json").exists() and (source / "candidate_sets.jsonl").exists():
        return "retrieval_matrix"
    if (source / "config.yaml").exists() and (source / "candidate_lists.jsonl").exists():
        return "ranking_experiment"
    raise ValueError(f"Unrecognized --candidates-from directory: {source}")


def _parse_scorer_specs(weights: list[float], extra_variants: list[str] | None) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for w in weights:
        name = "baseline" if np.isclose(w, 1e-6, rtol=0, atol=1e-15) else f"popularity_weight_{w:g}"
        if name in specs:
            raise ValueError("scorer variant names collide")
        specs[name] = {"kind": "baseline", "popularity_weight": float(w)}
    for raw in extra_variants or []:
        token = raw.strip()
        if not token:
            continue
        if token.startswith("hybrid_w"):
            w = float(token[len("hybrid_w"):])
            if not np.isfinite(w) or w < 0:
                raise ValueError(f"invalid hybrid scorer weight: {token}")
            spec = {"kind": "hybrid", "popularity_weight": w}
        elif token == "evidence_cf_ties":
            spec = {"kind": "evidence", "mode": "cf_ties", "popularity_weight": 0.1, "evidence_weight": 0.1}
        elif token == "evidence_additive":
            spec = {"kind": "evidence", "mode": "additive_ablation", "popularity_weight": 0.1, "evidence_weight": 0.1}
        elif token == "evidence_normalized":
            spec = {"kind": "evidence", "mode": "normalized_blend", "cf_weight": 0.2, "popularity_weight": 0.5, "evidence_weight": 1.0}
        elif token == "ltr_reranker":
            spec = {"kind": "ltr", "popularity_weight": None}
        else:
            raise ValueError(f"unsupported scorer variant: {token}")
        if token in specs:
            raise ValueError(f"duplicate scorer variant: {token}")
        specs[token] = spec
    return specs


def _embedding_identity(embeddings_path: Path | None, corpus_path: Path) -> dict[str, Any]:
    if embeddings_path is None:
        raise ValueError("hybrid retrieval requires --embeddings-path (or existing tag embedding artifact)")
    resolved = embeddings_path.resolve()
    if resolved.is_dir():
        manifest_path = resolved / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"embedding artifact directory missing manifest.json: {resolved}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "path": str(resolved),
            "manifest_sha256": file_hash(manifest_path),
            "build_id": manifest.get("build_id"),
            "corpus_sha256": file_hash(corpus_path) if corpus_path.exists() else None,
        }
    if not resolved.exists():
        raise ValueError(f"embedding artifact not found: {resolved}")
    sidecar = resolved.with_suffix(".meta.json")
    return {
        "path": str(resolved),
        "artifact_sha256": file_hash(resolved),
        "sidecar_sha256": file_hash(sidecar) if sidecar.exists() else None,
        "corpus_sha256": file_hash(corpus_path) if corpus_path.exists() else None,
    }


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


from package.evaluation.recommender.experiment.ranking_run_store import RankingRunStore
from package.evaluation.recommender.utils import StageProgress
from package.evaluation.recommender.experiment.ranking_stream_summary import RankingStreamSummary
from package.evaluation.recommender.experiment.save_experiment import _source_fingerprint, _environment_versions
from package.recommenders.shared.save_item_knn import save_item_knn
from package.recommenders.shared.load_item_knn import load_item_knn


def _load_eval_splits(paths, eval_on: str):
    """Load only frames required by this temporal evaluation.

    Validation does not need the test rows in memory. Test evaluation still
    loads train+validation for fitting and test as its target.
    """
    columns = ["user_idx", "item_idx", "timestamp"]
    train = pd.read_parquet(paths.split_path("train"), columns=columns)
    if eval_on == "validation":
        validation = pd.read_parquet(paths.split_path("validation"), columns=columns)
        test = pd.DataFrame(columns=columns)
    elif eval_on == "test":
        validation = pd.read_parquet(paths.split_path("validation"), columns=columns)
        test = pd.read_parquet(paths.split_path("test"), columns=columns)
    else:
        raise ValueError(f"unsupported evaluation split: {eval_on}")
    return train, validation, test


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", action="append",
                    help="Domain của bundle dữ liệu (lặp lại). Mặc định: tất cả -> 'multi_domain'; "
                         "1 domain -> bundle tên domain; tập con khác bị từ chối.")
    ap.add_argument("--eval-on", choices=("validation", "test"), default="validation")
    ap.add_argument("--work-dir", type=Path, help="Durable checkpoint directory; reuse with --resume")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--candidates-from", type=Path,
                    help="Freeze candidates from a compatible completed ranking experiment or retrieval matrix")
    ap.add_argument("--tag", help="Explicit existing bundle; does not bypass manifest validation")
    ap.add_argument("--retrieval", choices=("bm25", "hybrid"), default=None,
                    help="Retrieval mode for SearchTool when not replaying frozen candidates")
    ap.add_argument("--embeddings-path", type=Path, default=None,
                    help="Validated embedding artifact directory/NPZ for hybrid retrieval")
    ap.add_argument("--matrix-mode", default="recency_weighted",
                    help="Query mode to import when --candidates-from points to a retrieval matrix")
    ap.add_argument("--matrix-budget", type=int, default=None,
                    help="Candidate budget to import from retrieval matrix (default: candidate_budget)")
    ap.add_argument("--matrix-pools", default="bm25,hybrid,fused",
                    help="Comma-separated matrix pool names to replay (e.g. bm25,hybrid,fused)")
    ap.add_argument("--scorer-variants", default=None,
                    help="Extra scorer variants (comma-separated: hybrid_w4,evidence_cf_ties,evidence_additive,evidence_normalized,ltr_reranker)")
    ap.add_argument("--reranker-path", type=Path, default=None,
                    help="Persisted MultiSignalReranker artifact directory (required when ltr_reranker is selected)")
    args = ap.parse_args()

    # Mọi tham số đánh giá đọc từ configs/eval/ranking_eval.yaml (+ baselines/segment_thresholds/tools).
    cfg = load_config("eval/ranking_eval")["ranking_eval"]
    baselines = load_config("eval/baselines")["baselines"]
    args.all_users = bool(cfg.get("all_users", False))
    args.exclude_users_from = [str(p) for p in cfg.get("exclude_users_from", [])]
    args.per_segment = int(cfg["per_segment"])
    args.seed = int(baselines["seed"])  # single seed source: eval/baselines.baselines.seed
    args.candidate_budget = int(cfg["candidate_budget"])
    args.seed_items = int(cfg["seed_items"])
    args.query_items = int(cfg["query_items"])
    args.neighbors = int(baselines["item_knn"]["k"])  # baselines.item_knn.k
    args.ks = ",".join(str(k) for k in cfg["ks"])
    args.popularity_weights = ",".join(repr(float(w)) for w in cfg["popularity_weights"])
    args.metadata_policy = str(cfg["metadata_policy"])
    args.query_normalization = str(cfg["query_normalization"])
    args.use_prebuilt_corpus = bool(cfg["use_prebuilt_corpus"])
    args.allow_missing_corpus_sources = bool(cfg["allow_missing_corpus_sources"])
    args.batch_size = int(cfg["batch_size"])
    args.progress_every = int(cfg["progress_every"])
    args.retrieval = args.retrieval or str(cfg.get("retrieval", "bm25"))
    if args.embeddings_path is None and cfg.get("embeddings_path"):
        args.embeddings_path = Path(str(cfg["embeddings_path"]))
    if args.matrix_budget is None:
        args.matrix_budget = args.candidate_budget
    extra_variants_raw = args.scorer_variants if args.scorer_variants is not None else cfg.get("scorer_variants", [])
    if isinstance(extra_variants_raw, str):
        extra_variants = [x.strip() for x in extra_variants_raw.split(",") if x.strip()]
    else:
        extra_variants = [str(x).strip() for x in (extra_variants_raw or []) if str(x).strip()]
    args.extra_scorer_variants = extra_variants

    if args.per_segment < 1 or args.candidate_budget < 1:
        raise SystemExit("ranking_eval.per_segment and ranking_eval.candidate_budget must be positive")
    ks = sorted({int(x) for x in args.ks.split(",") if x.strip()})
    weights = [float(x) for x in args.popularity_weights.split(",") if x.strip()]
    if not ks or min(ks) < 1 or max(ks) > args.candidate_budget * 3:
        raise SystemExit("ranking_eval.ks must contain positive cutoffs no greater than 3*candidate_budget")
    if not weights or any(not np.isfinite(w) or w < 0 for w in weights):
        raise SystemExit("ranking_eval.popularity_weights must be finite and non-negative")
    if len(set(weights)) != len(weights):
        raise SystemExit("ranking_eval.popularity_weights must be unique")

    if args.batch_size < 1 or args.progress_every < 1 or args.seed_items < 1 or args.query_items < 1:
        raise SystemExit("ranking_eval.batch_size/progress_every/seed_items/query_items must be positive")
    if args.neighbors < 1:
        raise SystemExit("baselines.item_knn.k must be positive")
    if args.resume and args.work_dir is None:
        ap.error("--resume requires --work-dir")
    if args.candidate_budget > int(load_config("agent/tools")["tools"]["max_candidates"]):
        raise SystemExit("candidate-budget exceeds tools.max_candidates")
    from package.config.resolve_bundle_paths import resolve_bundle_paths
    paths = resolve_bundle_paths(tag=args.tag, domains=args.domain)
    tag_manifest = verify_tag_manifest(paths, domains=args.domain or get_domains())
    if tag_manifest["status"] == "legacy_unmanifested":
        print("!!! WARNING: tag has legacy artifacts without pipeline manifests; results will be marked legacy_unmanifested.", flush=True)
    elif tag_manifest["warnings"]:
        print(f"!!! WARNING: tag manifest chain has warnings: {tag_manifest['warnings']}", flush=True)
    meta_files = [(d, str(paths.meta_path(d))) for d in (args.domain or get_domains())]
    exp_root = paths.output_dir("ranking_eval")
    work = args.work_dir or (exp_root / "_checkpoints" / (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]))
    print(f"[checkpoint] {work.resolve()} (resume with --work-dir and --resume)", flush=True)
    provenance_started = time.perf_counter()
    print("[provenance] hashing input files; ETA unknown until completed", flush=True)
    identity = {
        "audit_profile": tag_manifest.get("audit_profile"),
        "format": 1, "source_fingerprint": _source_fingerprint(), "environment": _environment_versions(),
        "parameters": {k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()
                       if k not in {"resume", "work_dir", "batch_size", "progress_every", "experiments_dir"}},
        "effective_neighbors": args.neighbors,
        "split_files": {name:{"path":str(paths.split_path(name)), "sha256":file_hash(paths.split_path(name))} for name in ("train","validation","test")},
        "mapping_files": {str(f.resolve()):file_hash(f) for f in sorted(paths.mapped_dir.glob("*.json"))},
        "metadata_files": {d:{"path":str(Path(f).resolve()), "sha256":file_hash(f) if Path(f).exists() else None} for d,f in meta_files},
    }
    if not identity["mapping_files"]:
        raise ValueError("no mapping JSON files found")
    identity["exclusion_manifests"] = [{"path": str(p.resolve()), "sha256": file_hash(p)}
                                       for p in map(Path, args.exclude_users_from)]
    identity["parameters"]["exclude_users_from"] = [str(Path(p).resolve()) for p in args.exclude_users_from]
    if args.candidates_from:
        source_kind = _frozen_source_kind(args.candidates_from)
        required = MATRIX_REQUIRED_FILES if source_kind == "retrieval_matrix" else RANKING_REQUIRED_FILES
        identity["frozen_source_kind"] = source_kind
        identity["frozen_artifacts"] = {name: file_hash(args.candidates_from / name) for name in required}
    else:
        source_kind = None
    if args.retrieval == "hybrid" and not args.candidates_from:
        emb_path = args.embeddings_path or (paths.corpus_dir / f"item_embeddings_{paths.tag}.npz")
        identity["embedding_artifact"] = _embedding_identity(emb_path, paths.corpus_path)
    elif args.embeddings_path is not None:
        identity["embedding_artifact"] = _embedding_identity(args.embeddings_path, paths.corpus_path)

    scorer_specs = _parse_scorer_specs(weights, args.extra_scorer_variants)
    if any(s["kind"] == "ltr" for s in scorer_specs.values()):
        if args.reranker_path is None:
            raise ValueError("ltr_reranker scorer variant requires --reranker-path")
        rr_dir = args.reranker_path.resolve()
        rr_manifest_path = rr_dir / "manifest.json"
        if not rr_manifest_path.exists():
            raise ValueError(f"reranker artifact missing manifest.json: {rr_dir}")
        rr_manifest = json.loads(rr_manifest_path.read_text(encoding="utf-8"))
        identity["reranker_artifact"] = {
            "path": str(rr_dir),
            "manifest_sha256": file_hash(rr_manifest_path),
            "model_sha256": rr_manifest.get("checksums", {}).get("reranker.pkl"),
        }
    variants = {name: spec.get("popularity_weight") for name, spec in scorer_specs.items()}
    if source_kind == "ranking_experiment":
        if "baseline" not in variants:
            raise ValueError("frozen-candidate confirmation requires including baseline weight 1e-6")
        variants = {"baseline":variants["baseline"], **{k:v for k,v in variants.items() if k != "baseline"}}
        scorer_specs = {"baseline": scorer_specs["baseline"], **{k: v for k, v in scorer_specs.items() if k != "baseline"}}
    merges = (tuple(p.strip() for p in args.matrix_pools.split(",") if p.strip())
              if source_kind == "retrieval_matrix" else MERGES)
    if not merges or len(set(merges)) != len(merges):
        raise ValueError("matrix pools / merges must be unique non-empty names")
    identity["merges"] = list(merges)
    identity["scorer_specs"] = scorer_specs
    provenance_seconds = time.perf_counter() - provenance_started
    with RankingRunStore(work, identity, resume=args.resume) as store:
        store.put("startup_verification_seconds",store.get("startup_verification_seconds",0.) + provenance_seconds)
        publication = store.get("publication_destination")
        if publication and Path(publication).exists():
            published = Path(publication)
            manifest = published / "artifact_hashes.json"
            if manifest.exists():
                hashes = json.loads(manifest.read_text(encoding="utf-8"))
                document = yaml.safe_load((published/"config.yaml").read_text(encoding="utf-8"))
                if document["config"].get("checkpoint_identity") == identity:
                    if not all(file_hash(published/n) == h for n,h in hashes.items()):
                        raise ValueError("published artifact checksum mismatch")
                    store.put("final_experiment",str(published.resolve()))
        if store.get("final_experiment"):
            print(f"Already completed: {store.get('final_experiment')}", flush=True)
            return
        store.put("execution_sessions", store.get("execution_sessions",[]) + [{"batch_size":args.batch_size, "progress_every":args.progress_every, "resume":args.resume}])
        if not store.get("scoring_complete"):
            _run_stages(args, paths, meta_files, store, ks, variants, scorer_specs, merges, source_kind, tag_manifest)
        _finalize(args, paths, store, ks, variants, merges, exp_root)


def _run_stages(args, paths, meta_files, store, ks, variants, scorer_specs, merges, source_kind, tag_manifest):
    print("[splits] loading and sampling; ETA unknown", flush=True)
    train, validation, test = _load_eval_splits(paths, args.eval_on)
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
    excluded = confirmation_cohort(args.exclude_users_from, tag=paths.tag,
                                   split=args.eval_on, user_hash=mapping_hash(user2id),
                                   item_hash=mapping_hash(item2id))
    segments_by_user = {u: s for u, s in segments_by_user.items() if u not in excluded}
    if source_kind == "retrieval_matrix":
        matrix_doc = json.loads((args.candidates_from / "config.json").read_text(encoding="utf-8"))
        raw_cohort = matrix_doc.get("cohort", {})
        sampled = {seg: [int(u) for u in raw_cohort.get(seg, [])] for seg in SEGMENTS}
        for seg, group in sampled.items():
            for u in group:
                if segments_by_user.get(u) != seg:
                    raise ValueError(f"frozen matrix user {u} segment mismatch: expected {seg}, got {segments_by_user.get(u)}")
    else:
        sampled = ({segment: sorted(u for u, s in segments_by_user.items() if s == segment) for segment in SEGMENTS}
                   if args.all_users else sample_users(segments_by_user, args.per_segment, np.random.default_rng(args.seed)))
        if excluded and not args.all_users and any(len(group) != args.per_segment for group in sampled.values()):
            raise ValueError("insufficient untouched users for requested per-segment sample")
    users = {u for group in sampled.values() for u in group}
    sampled_fit = fit_df[fit_df["user_idx"].isin(users)]
    sampled_fit = sampled_fit.sort_values("timestamp")
    recent = sampled_fit.groupby("user_idx")["item_idx"].apply(lambda s: list(s)[::-1]).to_dict()
    seen_of = {u: set(recent.get(u, [])) for u in users}

    print("[corpus] start; ETA unknown", flush=True)
    if paths.corpus_path.exists() and args.use_prebuilt_corpus:
        corpus, coverage = load_corpus(
            paths.corpus_path, meta_files, item2id,
            float(load_config("agent/agent_eval")["agent_eval"]["min_metadata_coverage"]),
            allow_missing_sources=args.allow_missing_corpus_sources,
        )
    else:
        first_seen_ts = build_first_seen_timestamps([(d, paths.cleaned_path(d)) for d, _ in meta_files])
        corpus, _, coverage = build_corpus(
            meta_files, item2id,
            float(load_config("agent/agent_eval")["agent_eval"]["min_metadata_coverage"]),
            first_seen_ts=first_seen_ts,
        )

    metadata_policy = apply_metadata_policy(corpus, args.metadata_policy, as_of_timestamp=int(target_df.timestamp.min()))
    protocol_manifest = evaluation_protocol(eval_on=args.eval_on, tag=paths.tag, fit_df=fit_df,
        target_df=target_df, user2id=user2id, item2id=item2id, segments=segments_by_user,
        sampled=sampled, metadata_policy=metadata_policy,
        cohort_policy=cohort_policy_for_paths(paths))

    protocol_manifest["query_normalization"] = args.query_normalization
    protocol_manifest["sampling"] = ("all target-bearing users after declared exclusions; no segment cap"
                                     if args.all_users else protocol_manifest["sampling"])

    neighbors = args.neighbors
    knn_started = time.perf_counter()
    local_knn = store.path / "fit_item_knn.npz"
    context = dict(user2id=user2id, item2id=item2id, eval_on=args.eval_on, tag=paths.tag)
    knn = build_core_model(paths, args.eval_on, neighbors, fit_df, user2id, item2id)
    if knn is not None:
        knn_hash = knn._fit_data_hash
        protocol_manifest["item_knn"] = knn._evaluation_fit_provenance
        protocol_manifest["cf_history"] = "all pre-target history; similarity and popularity frozen on train_core"
    elif local_knn.exists() and local_knn.with_suffix(".meta.json").exists():
        print("[ItemKNN] validating local checkpoint model", flush=True)
        knn = load_item_knn(local_knn, neighbors, fit_df[["user_idx", "item_idx"]], **context)
        knn_hash = knn._fit_data_hash
    else:
        print("[ItemKNN] fitting; ETA unknown", flush=True)
        knn = ItemKNNRecommender(neighbors=neighbors).fit(fit_df[["user_idx", "item_idx"]])
        knn._fit_time = time.perf_counter() - knn_started
        save_item_knn(knn, local_knn, neighbors, fit_df[["user_idx", "item_idx"]], **context)
        knn_hash = item_knn_data_hash(fit_df[["user_idx", "item_idx"]])
    knn_seconds = time.perf_counter() - knn_started
    print(f"[ItemKNN] ready in {knn_seconds:.1f}s", flush=True)
    item_cf = SimilarTool(knn, item2id, corpus=corpus, logger=ToolCallLogger())
    embedding_provenance = None
    if args.retrieval == "hybrid" and not args.candidates_from:
        from scripts.data_pipeline.build_item_embeddings import load_validated_embeddings
        from package.embeddings import TextEncoder
        emb_path = args.embeddings_path or (paths.corpus_dir / f"item_embeddings_{paths.tag}.npz")
        vector_store, encoder_impl, embedding_provenance = load_validated_embeddings(emb_path, paths.corpus_path)
        query_encoder = TextEncoder(encoder_impl.encode, dimension=vector_store.dimension)
        semantic = SearchTool(corpus, logger=ToolCallLogger(), vector_store=vector_store, query_encoder=query_encoder, rrf_k=60)
        print(f"[hybrid] SearchTool ready: {len(vector_store):,} vectors, provider={embedding_provenance['provider']}", flush=True)
    else:
        semantic = SearchTool(corpus, logger=ToolCallLogger())
    query_tool = LookupTool(corpus, logger=ToolCallLogger())
    get_text = item_text_tables(corpus, namespaced)
    popularity = (knn.scores if hasattr(knn, "_evaluation_fit_provenance")
                  else np.asarray(fit_matrix.sum(axis=0)).ravel())
    popular_order = np.argsort(-popularity, kind="stable")
    max_candidates = int(load_config("agent/tools")["tools"]["max_candidates"])

    max_sampled_user = max(users) if users else 0
    metadata = {
        "tag": paths.tag, "splits_dir": str(paths.splits_dir), "eval_on": args.eval_on,
        "num_users": num_users, "num_items": num_items,
        "mapping_hash": mapping_hash(item2id), "user_mapping_hash": mapping_hash(user2id),
        "mapping_hash_protocol": "sorted_key_index_json_v1",
        "split_files": {
            name: {"path": str(paths.split_path(name)), "size_bytes": paths.split_path(name).stat().st_size,
                   "mtime_ns": paths.split_path(name).stat().st_mtime_ns, "sha256": file_hash(paths.split_path(name))}
            for name in ("train", "validation", "test")
        },
    }
    config = {
        "manifest_status": tag_manifest["status"],
        "manifest_sha256": tag_manifest["manifest_sha256"],
        "audit_profile": tag_manifest.get("audit_profile"),
        "protocol": protocol_manifest,
        "seed": args.seed, "per_segment": args.per_segment, "sampled_user_ids": sampled,
        "cohort_exclusions": {"users": len(excluded), "manifests": store.get("identity").get("exclusion_manifests", []),
                              "scope": "disjoint from declared manifests only; not proof of never-inspected users"},
        "candidate_budget_per_source": args.matrix_budget if source_kind == "retrieval_matrix" else args.candidate_budget,
        "candidate_merges": list(merges),
        "retrieval": {"mode": args.retrieval,
                      "sources": ["popularity", "item_cf", "hybrid" if args.retrieval == "hybrid" else "semantic"],
                      "embeddings": embedding_provenance,
                      "seed_items": args.seed_items,
                      "query_items": args.query_items, "semantic_query_mode": "titles_from_fit_history",
                      "item_knn_neighbors": neighbors, "item_knn_fit_data_hash": knn_hash,
                      "item_knn_fit_seconds": getattr(knn,"_fit_time",None),
                      "item_knn_setup_seconds_this_session": knn_seconds},
        "scorers": {"type": "MultiScorer" if any(s["kind"] != "baseline" for s in scorer_specs.values()) else "BaselineScorer",
                    "specs": scorer_specs, "popularity_weights": list(variants.values()),
                    "baseline_weight": 1e-6, "same_saved_candidate_lists": True},
        "ks": ks,
        "target_protocol": f"{args.eval_on} interactions; ranking uses novel targets; candidate recall retains all targets",
        "corpus": {"path": str(paths.corpus_path) if paths.corpus_path.exists() and args.use_prebuilt_corpus else None,
                   "metadata_coverage": coverage,
                   "missing_sources": [p for _, p in meta_files if not Path(p).exists()],
                   "allow_missing_sources": args.allow_missing_corpus_sources,
                   "mode": "in_memory_build" if not args.use_prebuilt_corpus or not paths.corpus_path.exists() else "prebuilt"},
        "max_sampled_user_idx": max_sampled_user,
    }
    config["persistence"] = {"work_dir":str(store.path.resolve()), "batch_size":args.batch_size,
        "checkpoint_format": "sqlite_transactional_v1", "quality_independent_of_batch_size":True}
    store.put("config", config)
    store.put("dataset", metadata)
    total = sum(len(group) for group in sampled.values())
    store.put("total_users", total)
    if args.candidates_from:
        if source_kind == "retrieval_matrix":
            _import_matrix_candidates(args, store, config, metadata, merges=merges,
                                      targets=target_by_user, seen_of=seen_of, item2id=item2id, id2user=id2user)
        else:
            _import_candidates(args, store, config, metadata, targets=target_by_user, seen_of=seen_of, item2id=item2id)
    else:
        done = store.count("candidates")
        print(f"[retrieval] committed total={done}/{total}",flush=True)
        progress, active_segment = None, None
        offsets, offset = {}, 0
        for segment in SEGMENTS:
            offsets[segment] = offset
            offset += len(sampled[segment])
        batch = []
        sequence = ((u,seg) for seg in SEGMENTS for u in sampled[seg])
        for position,(user,segment) in enumerate(sequence):
            if position < done:
                continue
            if segment != active_segment:
                if batch:
                    store.append("candidates",batch)
                    batch.clear()
                if progress is not None:
                    progress.update(store.count("candidates")-offsets[active_segment],force=True)
                active_segment = segment
                progress = StageProgress("retrieval:"+segment,len(sampled[segment]),
                    completed=max(0,done-offsets[segment]),every=args.progress_every)
            seen = seen_of[user]
            ask = min(args.candidate_budget + len(seen), max_candidates)
            targets = set(target_by_user[user])
            novel = targets - seen
            popularity = [int(i) for i in popular_order[:ask]]

            recent_ids = recent.get(user, [])
            seed_names = _ids_to_namespaced(recent_ids[: args.seed_items], id2item)
            start = time.perf_counter()
            cf_result = item_cf(items=seed_names, top_k=ask) if seed_names else None
            cf_seconds = time.perf_counter() - start
            cf_ids = [item2id[c["item_id"]] for c in cf_result.data["candidates"] if c["item_id"] in item2id] if cf_result and cf_result.ok else []

            query_names = _ids_to_namespaced(recent_ids[: args.query_items], id2item)
            text_info = get_text(query_names)
            raw_query = " ".join(text_info[item][0] for item in query_names if item in text_info)
            query = normalize_query_text(raw_query, args.query_normalization)
            start = time.perf_counter()
            sem_result = semantic(query=query, limit=ask) if query.strip() else None
            sem_seconds = time.perf_counter() - start
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
            record = {
                "user_idx": int(user), "user_id": id2user[user], "segment": segment,
                "targets": sorted(targets), "targets_seen_in_fit": sorted(targets & seen),
                "targets_unseen_in_fit": sorted(novel),
                "seen_count": len(seen),
                "source_latency_seconds": {"item_cf":cf_seconds, "semantic":sem_seconds},
                "semantic_query": {"raw": raw_query, "sent": query, "normalization": args.query_normalization,
                                   "changed": raw_query != query, "empty_after_normalization": bool(raw_query.strip()) and not query.strip()},
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
            }
            batch.append((position, record))
            if len(batch) >= args.batch_size:
                store.append("candidates", batch)
                batch.clear()
                progress.update(store.count("candidates")-offsets[segment])
            item_cf.logger.records.clear()
            semantic.logger.records.clear()
        store.append("candidates", batch)
        if progress is not None:
            progress.update(store.count("candidates")-offsets[active_segment], force=True)
    if store.count("candidates") != total:
        raise ValueError("candidate checkpoint does not contain the complete sample")
    shared_baseline = BaselineScorer(knn)
    shared_ltr = None
    if any(s["kind"] == "ltr" for s in scorer_specs.values()):
        from package.tools.retrieval.domain_category_popularity import DomainCategoryPopularity
        estimator, _ = MultiSignalReranker.load_estimator(args.reranker_path)
        eligible_ids = set(id2item.values())
        dcp = DomainCategoryPopularity.from_corpus(corpus, _ids_to_namespaced(popular_order.tolist(), id2item), eligible_ids)
        shared_ltr = MultiSignalReranker(shared_baseline, estimator, id2item=id2item, domain_pop=dcp)
    for merge in merges:
        for variant, spec in scorer_specs.items():
            weight = spec.get("popularity_weight")
            stream = f"scored:{merge}:{variant}"
            done = store.count(stream)
            progress = StageProgress(stream, total, completed=done, every=args.progress_every)
            static_scorer = None
            if spec["kind"] == "baseline":
                static_scorer = BaselineScorer(knn, popularity_weight=spec["popularity_weight"])
            elif spec["kind"] == "hybrid":
                static_scorer = HybridScorer(knn, popularity_weight=spec["popularity_weight"])
            reco = RankTool(static_scorer, user2id, item2id, corpus=corpus) if static_scorer is not None else None
            batch = []
            for position,record in store.rows("candidates", start=done, batch_size=args.batch_size):
                user,segment = record["user_idx"],record["segment"]
                candidates = [item2id[i] for i in record["candidate_sets"][merge]]
                user_id = record["user_id"]
                active_reco = reco
                if active_reco is None:
                    if spec["kind"] == "ltr":
                        attr_map = {x["item_id"]: x for x in (record.get("source_evidence") or [])}
                        seen_names = _ids_to_namespaced(sorted(seen_of.get(user, set())), id2item)
                        req_ltr = shared_ltr.for_request(source_attribution=attr_map, seen_items=seen_names)
                        active_reco = RankTool(req_ltr, user2id, item2id, corpus=corpus)
                    else:
                        ev_rows = record.get("source_evidence") or []
                        peak = max((float(x["score"]) for x in ev_rows), default=1.0)
                        evidence = {item2id[x["item_id"]]: float(x["score"]) / peak
                                    for x in ev_rows if x["item_id"] in item2id and peak > 0}
                        ev_scorer = EvidenceScorer(
                            shared_baseline, evidence, mode=spec["mode"],
                            popularity_weight=spec["popularity_weight"],
                            evidence_weight=spec["evidence_weight"],
                            cf_weight=spec.get("cf_weight", 1.0),
                        )
                        active_reco = RankTool(ev_scorer, user2id, item2id, corpus=corpus)
                start = time.perf_counter()
                # Rank the complete fixed candidate list so tie rate and the max-K boundary tie
                # include the candidates immediately below the recommendation cutoff.
                output = active_reco.execute(
                    user_id=user_id, candidates=_ids_to_namespaced(candidates, id2item),
                    top_k=len(candidates), exclude_seen=True,
                ) if candidates else {"ranked":[], "excluded_seen":[], "unscored_item_ids":[]}
                elapsed = time.perf_counter() - start
                ranked_ids = [item2id[r["item_id"]] for r in output["ranked"] if r["item_id"] in item2id]
                rank_scores = np.asarray([r["score"] for r in output["ranked"]], dtype=np.float64)
                tie = _tie_stats(rank_scores, max(ks))

                top_ranked = output["ranked"][: max(ks)]
                start = time.perf_counter()
                fetched = query_tool.execute(item_ids=[r["item_id"] for r in top_ranked]) if top_ranked else {"items": []}
                fetch_seconds = time.perf_counter() - start
                fetch_ok = len(fetched.get("items", [])) == len(top_ranked)

                row = {
                    "request_id": f"{merge}:{user}", "user_idx": user, "segment": segment,
                    "merge": merge, "scorer": variant, "popularity_weight": weight,
                    "targets": record["targets"], "targets_unseen_in_fit": record["targets_unseen_in_fit"],
                    "candidate_ids": _ids_to_namespaced(candidates, id2item),
                    "ranked_ids": [r["item_id"] for r in output["ranked"]],
                    "scores": [r["score"] for r in output["ranked"]],
                    "excluded_seen": output["excluded_seen"], "unscored_item_ids": output["unscored_item_ids"],
                    "ranking_latency_seconds": elapsed,
                    "fetch_latency_seconds": fetch_seconds,
                    "fetch_success": fetch_ok,
                    "recommendations_at_max_k": [r["item_id"] for r in top_ranked],
                    "retrieval_raw_union_count": len(record["raw_union"]),
                    "retrieval_seen_dropped_count": len(record["raw_union"]) - len(record["raw_union_after_seen"]),
                    **tie,
                }
                batch.append((position,row))
                if len(batch) >= args.batch_size:
                    store.append(stream,batch)
                    batch.clear()
                    progress.update(store.count(stream))
            store.append(stream,batch)
            progress.update(store.count(stream), force=True)
            if store.count(stream) != total:
                raise ValueError("incomplete scoring checkpoint")
            if source_kind == "ranking_experiment" and variant == "baseline":
                _confirm_frozen_baseline(store,item2id,ks,merge,variants)
    store.put("scoring_complete", True)


def _import_matrix_candidates(args, store, config, metadata, *, merges, targets, seen_of, item2id, id2user):
    source = args.candidates_from
    completion = json.loads((source / "artifact_hashes.json").read_text(encoding="utf-8"))
    if completion.get("status") != "complete":
        raise ValueError("only completed retrieval matrix runs may be imported")
    for name in ("config.json", "candidate_sets.jsonl", "frozen.json"):
        if file_hash(source / name) != completion["hashes"][name]:
            raise ValueError(f"frozen matrix checksum mismatch: {name}")
    frozen = json.loads((source / "frozen.json").read_text(encoding="utf-8"))
    if file_hash(source / "candidate_sets.jsonl") != frozen["candidate_sets_sha256"]:
        raise ValueError("frozen matrix candidate_sets_sha256 mismatch")
    if file_hash(source / "config.json") != frozen["config_sha256"]:
        raise ValueError("frozen matrix config_sha256 mismatch")

    matrix_doc = json.loads((source / "config.json").read_text(encoding="utf-8"))
    prov = matrix_doc["provenance"]
    if prov["tag"] != metadata["tag"]:
        raise ValueError("frozen matrix dataset tag mismatch")
    if prov["mapping_hash"] != metadata["mapping_hash"] or prov["user_mapping_hash"] != metadata["user_mapping_hash"]:
        raise ValueError("frozen matrix mapping hash mismatch")
    for split_name, expected_hash in prov.get("split_hashes", {}).items():
        if metadata["split_files"][split_name]["sha256"] != expected_hash:
            raise ValueError(f"frozen matrix split hash mismatch: {split_name}")
    matrix_proto = prov["protocol"]
    if matrix_proto["item_knn"]["eval_on"] != metadata["eval_on"]:
        raise ValueError("frozen matrix eval_on mismatch")
    if matrix_proto["metadata_policy"] != config["protocol"]["metadata_policy"]:
        raise ValueError("frozen matrix metadata_policy mismatch")
    if prov.get("fit_hash") and prov["fit_hash"] != config["retrieval"]["item_knn_fit_data_hash"]:
        raise ValueError("frozen matrix ItemKNN fit_hash mismatch")

    matrix_cfg = matrix_doc["config"]
    if args.matrix_mode not in matrix_cfg["query_modes"]:
        raise ValueError(f"matrix mode {args.matrix_mode!r} not in {matrix_cfg['query_modes']}")
    if args.matrix_budget not in matrix_cfg["budgets"]:
        raise ValueError(f"matrix budget {args.matrix_budget} not in {matrix_cfg['budgets']}")

    config["frozen_candidates"] = {
        "kind": "retrieval_matrix",
        "experiment": str(source.resolve()),
        "sha256": frozen["candidate_sets_sha256"],
        "config_sha256": frozen["config_sha256"],
        "matrix_mode": args.matrix_mode,
        "matrix_budget": args.matrix_budget,
        "matrix_pools": list(merges),
        "embeddings": prov.get("embeddings"),
        "ann_build": matrix_doc.get("ann_build"),
        "latency": "retrieval latency copied from frozen retrieval matrix; this session does not rerun retrieval",
    }
    store.put("config", config)
    total = store.get("total_users")
    done = store.count("candidates")
    progress = StageProgress("import frozen matrix candidates", total, completed=done, every=args.progress_every)

    selected_rows: dict[tuple[int, str], dict[str, Any]] = {}
    with (source / "candidate_sets.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["mode"] != args.matrix_mode or row["budget"] != args.matrix_budget:
                continue
            key = (int(row["user_idx"]), str(row["segment"]))
            if key in selected_rows:
                raise ValueError(f"duplicate frozen matrix row for {key}")
            selected_rows[key] = row

    expected_order = [(u, seg) for seg in SEGMENTS for u in config["sampled_user_ids"][seg]]
    if len(selected_rows) != len(expected_order):
        raise ValueError(f"frozen matrix row count mismatch: expected {len(expected_order)}, got {len(selected_rows)}")

    batch = []
    for position, (u, seg) in enumerate(expected_order):
        row = selected_rows.get((u, seg))
        if row is None:
            raise ValueError(f"frozen matrix missing user {u} ({seg})")
        expected_novel = targets[u] - seen_of[u]
        row_targets_idx = {item2id[i] for i in row["targets"] if i in item2id}
        if len(row_targets_idx) != len(row["targets"]) or row_targets_idx != expected_novel:
            raise ValueError(f"frozen matrix targets mismatch for user {u}")
        seen_names = set(row["seen"])
        if {item2id[i] for i in seen_names if i in item2id} != seen_of[u]:
            raise ValueError(f"frozen matrix seen history mismatch for user {u}")
        pools = row["pools"]
        missing_pools = [m for m in merges if m not in pools]
        if missing_pools:
            raise ValueError(f"frozen matrix missing requested pools: {missing_pools}")
        candidate_sets = {}
        for m in merges:
            names = pools[m]
            if any(i not in item2id for i in names):
                raise ValueError(f"unknown frozen matrix candidate item in pool {m}")
            if len(names) != len(set(names)):
                raise ValueError(f"duplicate frozen matrix candidates in pool {m}")
            if seen_names & set(names):
                raise ValueError(f"frozen matrix pool {m} contains seen item for user {u}")
            candidate_sets[m] = names
        union_ids = list(dict.fromkeys(i for names in candidate_sets.values() for i in names))
        query_text = (row.get("query") or {}).get("text", "")
        lat = row.get("latency") or {}
        converted = {
            "user_idx": int(u),
            "user_id": id2user[u],
            "segment": seg,
            "targets": sorted(targets[u]),
            "targets_seen_in_fit": sorted(targets[u] & seen_of[u]),
            "targets_unseen_in_fit": sorted(expected_novel),
            "seen_count": len(seen_of[u]),
            "source_latency_seconds": {
                "item_cf": float(lat.get("item_cf", 0.0)),
                "semantic": float(lat.get("bm25", 0.0)) + float(lat.get("dense", 0.0)),
            },
            "semantic_query": {
                "raw": query_text, "sent": query_text, "normalization": matrix_cfg.get("normalization", "raw"),
                "changed": False, "empty_after_normalization": False,
            },
            "sources_raw": candidate_sets,
            "sources_after_seen_filter": candidate_sets,
            "raw_union": union_ids,
            "raw_union_after_seen": union_ids,
            "seen_filtered_union": union_ids,
            "candidate_sets": candidate_sets,
            "source_evidence": row.get("source_evidence", []),
            "source_failures": {"item_cf": None, "semantic": None},
        }
        if position < done:
            continue
        batch.append((position, converted))
        if len(batch) >= args.batch_size:
            store.append("candidates", batch)
            batch.clear()
            progress.update(store.count("candidates"))
    store.append("candidates", batch)
    progress.update(store.count("candidates"), force=True)


def _import_candidates(args, store, config, metadata, *, targets, seen_of, item2id):
    source = args.candidates_from
    document = yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8"))
    old, dataset = document["config"], document["run"]["dataset"]
    for key in ("tag", "eval_on", "mapping_hash", "user_mapping_hash"):
        if dataset[key] != metadata[key]:
            raise ValueError(f"frozen candidate dataset {key} mismatch")
    if {k:v["sha256"] for k,v in dataset["split_files"].items()} != {k:v["sha256"] for k,v in metadata["split_files"].items()}:
        raise ValueError("frozen candidate split content mismatch")
    for key in ("sampled_user_ids", "candidate_budget_per_source"):
        if old[key] != config[key]:
            raise ValueError(f"frozen candidate {key} mismatch")
    for key in ("seed_items", "query_items", "item_knn_neighbors", "item_knn_fit_data_hash"):
        if old["retrieval"][key] != config["retrieval"][key]:
            raise ValueError(f"frozen retrieval {key} mismatch")
    for key in ("metadata_policy", "label_policy", "cohort_policy", "history_size"):
        if old["protocol"][key] != config["protocol"][key]:
            raise ValueError(f"frozen protocol {key} mismatch")
    if old["protocol"].get("query_normalization", "raw") != args.query_normalization:
        raise ValueError("frozen candidate query normalization mismatch")
    metrics = json.loads((source / "metrics.json").read_text(encoding="utf-8"))
    store.put("frozen_retrieval_metrics", metrics["retrieval"])
    config["frozen_candidates"] = {"experiment":str(source.resolve()),
        "sha256":file_hash(source / "candidate_lists.jsonl"),
        "latency": "retrieval latency copied from source run; this session does not rerun retrieval",
        "source_metadata_snapshot": "use source checkpoint_identity when present; legacy source experiments may not record metadata content hashes"}
    store.put("config", config)
    total = store.get("total_users")
    done = store.count("candidates")
    progress = StageProgress("import frozen candidates", total, completed=done, every=args.progress_every)
    expected = iter((u,s) for s in SEGMENTS for u in config["sampled_user_ids"][s])
    batch, count = [], 0
    with (source / "candidate_lists.jsonl").open(encoding="utf-8") as stream:
        for position,line in enumerate(stream):
            row = json.loads(line)
            pair = next(expected, None)
            if pair != (row["user_idx"],row["segment"]):
                raise ValueError("frozen candidate order/user sample mismatch")
            u = row["user_idx"]
            if set(row["targets"]) != set(targets[u]) or set(row["targets_unseen_in_fit"]) != set(targets[u]) - seen_of[u]:
                raise ValueError("frozen ground truth/history mismatch")
            if set(row["candidate_sets"]) != set(MERGES):
                raise ValueError("frozen merge definitions mismatch")
            for names in row["candidate_sets"].values():
                if any(i not in item2id for i in names):
                    raise ValueError("unknown frozen candidate item")
                if len(names) != len(set(names)):
                    raise ValueError("duplicate frozen candidates")
            count += 1
            if position < done:
                continue
            batch.append((position,row))
            if len(batch) >= args.batch_size:
                store.append("candidates",batch)
                batch.clear()
                progress.update(store.count("candidates"))
    if count != total:
        raise ValueError("incomplete frozen candidate file")
    store.append("candidates",batch)
    progress.update(store.count("candidates"), force=True)


def _confirm_frozen_baseline(store,item2id,ks,merge,variants):
    source = Path(store.get("config")["frozen_candidates"]["experiment"])
    expected = json.loads((source/"metrics.json").read_text(encoding="utf-8"))["ranking"][merge]["baseline"]
    summary = RankingStreamSummary(item2id,ks)
    for _,row in store.rows(f"scored:{merge}:baseline"):
        summary.add_scored(row)
    actual = summary.result([merge],{"baseline":1e-6})["ranking"][merge]["baseline"]
    maximum = 0.
    for segment in SEGMENTS:
        a,b = actual["per_segment"][segment],expected["per_segment"][segment]
        if a["users"] != b["users"]:
            raise ValueError("baseline confirmation user denominator mismatch")
        for k,metrics in a["metrics"].items():
            if k not in b["metrics"]:
                raise ValueError("source baseline lacks requested K; establish matching baseline first")
            for name,value in metrics.items():
                error = abs(value-b["metrics"][k][name])
                maximum = max(maximum,error)
                if error > 1e-12:
                    raise ValueError(f"baseline confirmation failed: {merge}/{segment}/{name}")
            if a["catalog_coverage"][k] != b["catalog_coverage"][k]:
                raise ValueError("baseline confirmation catalog coverage mismatch")
    reference_rows = 0
    current = iter(store.rows(f"scored:{merge}:baseline"))
    with (source/"scored.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            reference = json.loads(line)
            if reference["merge"] != merge or reference["scorer"] != "baseline":
                continue
            item = next(current,None)
            if item is None:
                raise ValueError("source baseline has extra users")
            _, row = item
            for key in ("user_idx", "candidate_ids", "ranked_ids", "targets_unseen_in_fit", "excluded_seen", "unscored_item_ids"):
                if row[key] != reference[key]:
                    raise ValueError(f"baseline per-user {key} mismatch")
            if len(row["scores"]) != len(reference["scores"]) or not np.allclose(row["scores"],reference["scores"],rtol=0,atol=1e-12):
                raise ValueError("baseline per-user scores mismatch")
            reference_rows += 1
    if next(current,None) is not None or reference_rows != store.get("total_users"):
        raise ValueError("source baseline is incomplete")
    store.put("confirmation:"+merge,{"source":str(source),"metric_abs_tolerance":1e-12,"maximum_metric_abs_error":maximum,
                                    "per_user_rank_and_score_confirmation":True,"users":reference_rows})
    print(f"[baseline confirmed] {merge}, max metric error={maximum:.3g}",flush=True)


def _finalize(args, paths, store, ks, variants, merges, exp_root):
    identity = store.get("identity")
    if _source_fingerprint() != identity["source_fingerprint"] or _environment_versions() != identity["environment"]:
        raise ValueError("implementation/environment changed during evaluation; results not published")
    print("[provenance] revalidating input hashes before publication",flush=True)
    inputs = list(identity["split_files"].values()) + list(identity["metadata_files"].values())
    inputs += [{"path":p,"sha256":h} for p,h in identity["mapping_files"].items()]
    for entry in inputs:
        path = Path(entry["path"])
        actual = file_hash(path) if path.exists() else None
        if actual != entry["sha256"]:
            raise ValueError(f"input changed during evaluation: {path}; results not published")
    if args.candidates_from:
        for name,digest in identity["frozen_artifacts"].items():
            if file_hash(args.candidates_from/name) != digest:
                raise ValueError("frozen source artifacts changed during evaluation")
    print("[summary] streaming persisted rows", flush=True)
    user_mapping, item2id = load_mappings(paths.mapped_dir)
    del user_mapping
    accumulator = RankingStreamSummary(item2id,ks)
    total = store.get("total_users")
    progress = StageProgress("summarize candidates",total,every=args.progress_every)
    for position,row in store.rows("candidates",batch_size=args.batch_size):
        accumulator.add_candidate(row)
        progress.update(position+1)
    streams = []
    for merge in merges:
        for variant in variants:
            stream = f"scored:{merge}:{variant}"
            streams.append(stream)
            if store.count(stream) != total:
                raise ValueError("cannot finalize incomplete scored stream")
            progress = StageProgress("summarize " + stream,total,every=args.progress_every)
            for position,row in store.rows(stream,batch_size=args.batch_size):
                accumulator.add_scored(row)
                progress.update(position+1)
    metrics = accumulator.result(merges, variants)
    frozen = store.get("frozen_retrieval_metrics")
    if frozen:
        for merge in merges:
            for segment in SEGMENTS:
                metrics["retrieval"][merge][segment]["candidate_generation_latency_seconds"] = frozen[merge][segment]["candidate_generation_latency_seconds"]
    is_frozen = bool(args.candidates_from)
    metrics["measurement_scope"] = "fixed_candidate_scoring" if is_frozen else "deterministic_retrieve_rank_fetch"
    metrics["tool_health_scope"] = "source retrieval records; no retrieval executed this session" if is_frozen else "retrieval records from observed sessions"
    config = store.get("config")
    config["checkpoint_identity"] = store.get("identity")
    config["persistence"]["execution_sessions"] = store.get("execution_sessions",[])
    config["baseline_confirmation"] = {m: store.get("confirmation:" + m) for m in merges}
    pending = store.path / "publication"
    pending.mkdir(exist_ok=True)
    print("[export] candidate/scored JSONL; ETA unknown", flush=True)
    store.export(["candidates"],pending/"candidate_lists.jsonl")
    store.export(streams,pending/"scored.jsonl")
    hashes = {name:file_hash(pending/name) for name in ("candidate_lists.jsonl","scored.jsonl")}
    (pending/"artifact_hashes.json").write_text(json.dumps(hashes,indent=2),encoding="utf-8")
    timing = store.timing()
    timing["startup_verification_seconds"] = store.get("startup_verification_seconds",0.)
    metrics["checkpoint_timing"] = timing
    metrics["runtime_seconds"] = timing["committed_active_seconds"] + timing["startup_verification_seconds"]
    config["retrieval_latency_provenance"] = "copied from frozen experiment" if is_frozen else "per-user timings persisted during retrieval"
    # A separate, fresh manifest directory tolerates interruption while writing.
    manifests = store.path / ("manifests_" + uuid.uuid4().hex)
    save_experiment(manifests,config=config,metrics=metrics,seed=args.seed,
                    dataset_info=store.get("dataset"),runtime_seconds=metrics["runtime_seconds"],
                    notes="Batch checkpoints; identical persisted candidates per scorer. Historical static-catalog proxy. Runtime through JSONL export, excludes downtime; see checkpoint_timing.")
    for name in ("config.yaml", "metrics.json", "README.md"):
        (manifests/name).replace(pending/name)
    manifests.rmdir()
    while True:
        destination = next_experiment_dir(exp_root)
        store.put("publication_destination",str(destination.resolve()))
        try:
            pending.rename(destination)
            break
        except FileExistsError:
            continue
    store.put("final_experiment",str(destination.resolve()))
    print(f"Saved ranking evaluation: {destination}",flush=True)
    for merge in merges:
        for variant in variants:
            print(merge,variant,{s:metrics["ranking"][merge][variant]["per_segment"][s].get("metrics",{}).get("10",{}) for s in SEGMENTS},flush=True)


if __name__ == "__main__":
    main()
