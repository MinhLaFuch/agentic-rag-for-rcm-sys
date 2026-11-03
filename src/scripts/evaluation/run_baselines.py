"""
Chạy các baseline trên splits của stage 3.

    PYTHONPATH=. python scripts/evaluation/run_baselines.py --eval-on validation
    PYTHONPATH=. python scripts/evaluation/run_baselines.py --tag vg_toys --models popularity,item_knn
"""

import argparse
import math
import time
from pathlib import Path

from package.config import get_data_paths, load_config
from package.data.split import infer_matrix_shape, load_splits
from package.tools.evaluation.evaluate_recommender import evaluate_recommender
from package.tools.evaluation import next_experiment_dir, save_experiment, select_fit_target
from package.tools.recommenders import build_interaction_matrix, build_model
from package.data.mapping import load_mappings
from package.data.manifest import verify_tag_manifest
from package.tools.evaluation.build_core_model import build_core_model
from package.tools.evaluation.core_inputs import core_inputs
from package.tools.evaluation.global_core_pairs import global_core_pairs
from package.tools.evaluation.sha256_file import sha256_file
from package.tools.recommenders.hybrid_item_knn_recommender import HybridItemKNNRecommender
from package.utils import ensure_utf8_stdout


def main() -> None:
    ensure_utf8_stdout()

    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Tên lần chạy (mặc định: tag trong run_tag.yaml).")
    parser.add_argument("--splits-dir", help="Mặc định: <splits_dir>/<tag> trong data_paths.yaml.")
    parser.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    parser.add_argument("--models", help="Mặc định: baselines.models trong baselines.yaml.")
    parser.add_argument("--ks", default=None, help="vd: 5,10,20 (mac dinh lay tu recommendation_metrics.yaml)")
    parser.add_argument("--experiments-dir", help="Mặc định: experiments_dir trong data_paths.yaml.")
    parser.add_argument("--progress-every", type=int, default=10000, help="Print evaluation progress every N users or 10 seconds")
    parser.add_argument("--item-knn-hybrid-weight", type=float, help="Opt-in normalized CF + full pre-target-history popularity; choose on validation")
    parser.add_argument("--popularity-source", choices=("train_core", "full_history"), default="train_core",
                        help="Popularity control training source; full_history uses all pre-target history")
    args = parser.parse_args()
    if args.progress_every < 1:
        parser.error("--progress-every must be positive")
    if args.item_knn_hybrid_weight is not None and (not math.isfinite(args.item_knn_hybrid_weight) or args.item_knn_hybrid_weight < 0):
        parser.error("--item-knn-hybrid-weight must be finite and nonnegative")

    model_cfg = load_config("eval/baselines")["baselines"]
    eval_cfg = load_config("eval/recommendation_metrics")
    ks = [int(x) for x in args.ks.split(",")] if args.ks else eval_cfg["recommendation_metrics"]["k_values"]
    sparse_max = load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"]
    model_names = args.models.split(",") if args.models else model_cfg["models"]
    model_names = [m.strip() for m in model_names if m.strip()]
    paths = get_data_paths(args.tag)
    splits_dir = args.splits_dir or str(paths.splits_dir)

    if args.splits_dir and Path(args.splits_dir).resolve() != paths.splits_dir.resolve():
        parser.error("--splits-dir must match the selected tag; use --tag to select provenance")
    print("[startup] verifying manifest hashes; ETA unavailable", flush=True)
    manifest = verify_tag_manifest(paths)
    print("[startup] loading splits and building sparse matrices; ETA unavailable", flush=True)
    train, val, test = load_splits(splits_dir, ("user_idx", "item_idx", "timestamp"))
    num_users, num_items = infer_matrix_shape(train, val, test)

    fit_df, target_df = select_fit_target(train, val, test, args.eval_on)

    fit_matrix = build_interaction_matrix(fit_df, num_users, num_items)
    target_matrix = build_interaction_matrix(target_df, num_users, num_items)
    user2id, item2id = load_mappings(paths.mapped_dir)
    core = core_inputs(paths, user2id, item2id)
    training_matrix = (build_interaction_matrix(global_core_pairs(core), num_users, num_items)
                       if core is not None else fit_matrix)

    dataset_info = {
        "tag": paths.tag,
        "splits_dir": splits_dir,
        "eval_on": args.eval_on,
        "num_users": num_users,
        "num_items": num_items,
        "fit_interactions": int(fit_matrix.nnz),
        "target_interactions": int(target_matrix.nnz),
        "split_files": {
            name: {"path": str(Path(splits_dir) / f"{name}.parquet"),
                   "size_bytes": (Path(splits_dir) / f"{name}.parquet").stat().st_size,
                   "mtime_ns": (Path(splits_dir) / f"{name}.parquet").stat().st_mtime_ns,
                   "sha256": sha256_file(Path(splits_dir) / f"{name}.parquet")}
            for name in ("train", "validation", "test")
        },
    }
    print(f"=== BASELINE REPORT (eval_on={args.eval_on}) ===")
    print(f"dataset {dataset_info}")

    t_start = time.time()
    all_metrics = {}
    fit_splits_by_model = {}
    for name in model_names:
        print(f"[model:{name}] preparing model", flush=True)
        model = build_model(name, model_cfg)
        t0 = time.time()
        if name == "item_knn" and core is not None:
            compact = build_core_model(paths, args.eval_on, int(model_cfg["item_knn"]["k"]), fit_df, user2id, item2id)
            primary = getattr(model, "primary", model)
            primary.train_matrix = training_matrix
            primary.num_users, primary.num_items = training_matrix.shape
            primary.similarity = compact.similarity.T.tocsr()
            if primary is not model:
                model.train_matrix = training_matrix
                model.num_users, model.num_items = training_matrix.shape
                model.fallback.fit(training_matrix)
        else:
            model.fit(fit_matrix if name == "popularity" and args.popularity_source == "full_history" else training_matrix)
            if name == "popularity" and args.popularity_source == "full_history":
                model.name = "history_popularity"
                # Keep the same core-item metric buckets as exp_004/005.
                model.item_familiarity_matrix = training_matrix
        def attach_history(current):
            current.history_matrix = fit_matrix
            for attribute in ("primary", "fallback"):
                child = getattr(current, attribute, None)
                if child is not None:
                    attach_history(child)
        attach_history(model)
        if name == "item_knn" and args.item_knn_hybrid_weight is not None:
            primary = getattr(model, "primary", model)
            model = HybridItemKNNRecommender(primary, fit_matrix, args.item_knn_hybrid_weight)
        fit_seconds = time.time() - t0

        result = evaluate_recommender(model, fit_matrix, target_matrix, ks, sparse_max=sparse_max,
                                      progress_every=args.progress_every)
        all_metrics[model.name] = result.to_metrics(fit_seconds)
        fit_splits_by_model[model.name] = (
            (["train"] if args.eval_on == "validation" else ["train", "validation"])
            if name == "popularity" and args.popularity_source == "full_history"
            else (["train_core"] if core is not None else (["train"] if args.eval_on == "validation" else ["train", "validation"])))

        k0 = ks[0] if 10 not in ks else 10
        o, w = result.overall, result.by_segment.get("warm", {})
        print(
            f"model={model.name} fit_s={fit_seconds:.1f} "
            f"recall@{k0}={o[f'recall@{k0}']:.4f} ndcg@{k0}={o[f'ndcg@{k0}']:.4f} "
            f"hit@{k0}={o[f'hit_rate@{k0}']:.4f} mrr@{k0}={o[f'mrr@{k0}']:.4f} "
            f"warm_recall@{k0}={w.get(f'recall@{k0}', float('nan')):.4f} "
            f"users={result.num_users}"
        )

    exp_dir = save_experiment(
        next_experiment_dir(args.experiments_dir or paths.experiments_dir),
        config={"manifest_status": manifest["status"], "manifest_sha256": manifest["manifest_sha256"],
                "item_knn_hybrid_weight": args.item_knn_hybrid_weight,
                "hybrid_popularity_source": "full pre-target history" if args.item_knn_hybrid_weight is not None else None,
                "popularity_source": args.popularity_source,
                "item_familiarity_source": "train_core" if core is not None else "pre-target history",
                "fit_splits_by_model": fit_splits_by_model,
                "fit_splits": ["train_core"] if core is not None else (["train"] if args.eval_on == "validation" else ["train", "validation"]),
                "population": "all target-bearing users; segments and exclusion use full pre-target history",
                "models": model_names, "ks": ks, "sparse_max": sparse_max, "baselines": model_cfg},
        metrics=all_metrics,
        seed=model_cfg.get("seed", 42),
        dataset_info=dataset_info,
        runtime_seconds=time.time() - t_start,
    )
    print(f"saved experiment -> {exp_dir}")
    print("=== END REPORT ===")


if __name__ == "__main__":
    main()
