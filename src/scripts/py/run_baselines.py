"""
Chạy các baseline trên splits của stage 3.

    PYTHONPATH=. python scripts/py/run_baselines.py --eval-on validation
    PYTHONPATH=. python scripts/py/run_baselines.py --tag vg_toys --models popularity,item_knn
"""

import argparse
import time

import pandas as pd

from package.config import get_data_paths, load_config
from package.data.split import infer_matrix_shape, load_splits
from package.tools.evaluation.evaluator import evaluate_recommender
from package.tools.evaluation import next_experiment_dir, save_experiment
from package.tools.recommenders import build_interaction_matrix, build_model
from package.utils.console import ensure_utf8_stdout


def main() -> None:
    ensure_utf8_stdout()

    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Tên lần chạy (mặc định: tag trong run_tag.yaml).")
    parser.add_argument("--splits-dir", help="Mặc định: <splits_dir>/<tag> trong data_paths.yaml.")
    parser.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    parser.add_argument("--models", help="Mặc định: baselines.models trong baselines.yaml.")
    parser.add_argument("--ks", default=None, help="vd: 5,10,20 (mac dinh lay tu recommendation_metrics.yaml)")
    parser.add_argument("--experiments-dir", help="Mặc định: experiments_dir trong data_paths.yaml.")
    args = parser.parse_args()

    model_cfg = load_config("eval/baselines")["baselines"]
    eval_cfg = load_config("eval/recommendation_metrics")
    ks = [int(x) for x in args.ks.split(",")] if args.ks else eval_cfg["recommendation_metrics"]["k_values"]
    sparse_max = load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"]
    model_names = args.models.split(",") if args.models else model_cfg["models"]
    model_names = [m.strip() for m in model_names if m.strip()]
    paths = get_data_paths(args.tag)
    splits_dir = args.splits_dir or str(paths.splits_dir)

    train, val, test = load_splits(splits_dir)
    num_users, num_items = infer_matrix_shape(train, val, test)

    if args.eval_on == "validation":
        fit_df, target_df = train, val
    else:
        fit_df, target_df = pd.concat([train, val], ignore_index=True), test

    fit_matrix = build_interaction_matrix(fit_df, num_users, num_items)
    target_matrix = build_interaction_matrix(target_df, num_users, num_items)

    dataset_info = {
        "splits_dir": splits_dir,
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
        next_experiment_dir(args.experiments_dir or paths.experiments_dir),
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