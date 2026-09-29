"""
    PYTHONPATH=. python scripts/run_baselines.py \
        --splits-dir data/splits/multi_domain --eval-on validation
"""

import argparse
import time

import pandas as pd

from src.config.loader import load_config
from src.data.interactions import build_interaction_matrix
from src.evaluation.evaluator import evaluate_recommender
from src.evaluation.experiment_log import next_experiment_dir, save_experiment
from src.recommenders.base import Recommender
from src.recommenders.bpr_mf import BPRMFRecommender
from src.recommenders.fallback import FallbackRecommender
from src.recommenders.item_knn import ItemKNNRecommender
from src.recommenders.popularity import PopularityRecommender
from src.recommenders.random_rec import RandomRecommender
from src.utils.console import ensure_utf8_stdout

ALL_MODELS = ["random", "popularity", "item_knn", "bpr_mf"]


def build_model(name: str, cfg: dict) -> Recommender:
    seed = cfg.get("seed", 42)
    if name == "random":
        return RandomRecommender(seed=seed)
    if name == "popularity":
        return PopularityRecommender()

    if name == "item_knn":
        model: Recommender = ItemKNNRecommender(**cfg.get("item_knn", {}))
    elif name == "bpr_mf":
        model = BPRMFRecommender(seed=seed, **cfg.get("bpr_mf", {}))
    else:
        raise ValueError(f"Unknown model '{name}'. Choose from {ALL_MODELS}")

    if cfg.get("popularity_fallback", True):
        return FallbackRecommender(model, PopularityRecommender())
    return model


def main() -> None:
    ensure_utf8_stdout()

    parser = argparse.ArgumentParser()
    parser.add_argument("--splits-dir", required=True)
    parser.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    parser.add_argument("--models", default=",".join(ALL_MODELS))
    parser.add_argument("--ks", default=None, help="vd: 5,10,20 (mac dinh lay tu evaluation.yaml)")
    parser.add_argument("--experiments-dir", default="experiments")
    args = parser.parse_args()

    model_cfg = load_config("model")["baselines"]
    eval_cfg = load_config("evaluation")
    ks = [int(x) for x in args.ks.split(",")] if args.ks else eval_cfg["recommendation_metrics"]["k_values"]
    sparse_max = eval_cfg["segment_thresholds"]["sparse_max_history"]
    model_names = [m.strip() for m in args.models.split(",") if m.strip()]

    cols = ["user_idx", "item_idx"]
    train = pd.read_parquet(f"{args.splits_dir}/train.parquet", columns=cols)
    val = pd.read_parquet(f"{args.splits_dir}/validation.parquet", columns=cols)
    test = pd.read_parquet(f"{args.splits_dir}/test.parquet", columns=cols)

    num_users = int(max(d["user_idx"].max() for d in (train, val, test))) + 1
    num_items = int(max(d["item_idx"].max() for d in (train, val, test))) + 1

    if args.eval_on == "validation":
        fit_df, target_df = train, val
    else:
        fit_df, target_df = pd.concat([train, val], ignore_index=True), test

    fit_matrix = build_interaction_matrix(fit_df, num_users, num_items)
    target_matrix = build_interaction_matrix(target_df, num_users, num_items)

    dataset_info = {
        "splits_dir": args.splits_dir,
        "eval_on": args.eval_on,
        "num_users": num_users,
        "num_items": num_items,
        "fit_interactions": int(fit_matrix.nnz),
        "target_interactions": int(target_matrix.nnz),
    }
    print(f"=== BASELINE REPORT (eval_on={args.eval_on}) ===")
    print(f"dataset {dataset_info}")

    t_start = time.time()
    all_metrics = {}
    for name in model_names:
        model = build_model(name, model_cfg)
        t0 = time.time()
        model.fit(fit_matrix)
        fit_seconds = time.time() - t0

        result = evaluate_recommender(model, fit_matrix, target_matrix, ks, sparse_max=sparse_max)
        all_metrics[model.name] = {
            "overall": result.overall,
            "by_segment": result.by_segment,
            "num_users": result.num_users,
            "catalog_coverage": result.catalog_coverage,
            "target_item_seen_ratio": result.target_item_seen_ratio,
            "fit_seconds": round(fit_seconds, 2),
        }

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
        next_experiment_dir(args.experiments_dir),
        config={"models": model_names, "ks": ks, "sparse_max": sparse_max, "baselines": model_cfg},
        metrics=all_metrics,
        seed=model_cfg.get("seed", 42),
        dataset_info=dataset_info,
        runtime_seconds=time.time() - t_start,
    )
    print(f"saved experiment -> {exp_dir}")
    print("=== END REPORT ===")


if __name__ == "__main__":
    main()