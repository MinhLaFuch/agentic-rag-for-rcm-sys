"""
Chạy các baseline trên splits của stage 3.

    PYTHONPATH=. python scripts/evaluation/run_baselines.py --eval-on validation
    PYTHONPATH=. python scripts/evaluation/run_baselines.py --domain Video_Games

Mọi tham số (models, ks, seed, tham số từng model, popularity_source,
item_knn_hybrid_weight) đọc từ
configs/eval/baselines.yaml, eval/recommendation_metrics.yaml, eval/segment_thresholds.yaml
và output dir từ data_paths.yaml — không có override flag.

Khi stage 3 ghi nhận ``data_protocol: temporal_train_core``, item_knn và các
model khác fit trên train-core (compact cache nếu có) trong khi seen-exclusion
và đánh giá vẫn dùng toàn bộ pre-target history — xem
``evaluation.recommender.analysis.core_inputs``.
"""

import argparse
import time
from pathlib import Path

from package.config import get_data_paths, load_config
from package.data.mapping import load_mappings
from package.data.split import infer_matrix_shape, load_splits
from package.evaluation.recommender.analysis.build_core_model import build_core_model
from package.evaluation.recommender.analysis.core_inputs import core_inputs
from package.evaluation.recommender.analysis.global_core_pairs import global_core_pairs
from package.evaluation.recommender.core import evaluate_recommender
from package.evaluation.recommender.experiment import next_experiment_dir, save_experiment
from package.evaluation.recommender.config import select_fit_target
from package.evaluation.recommender.utils import sha256_file
from package.recommenders.evaluation.hybrid_item_knn_recommender import HybridItemKNNRecommender
from package.recommenders.shared import build_interaction_matrix, build_model
from package.utils import ensure_utf8_stdout


def _attach_history(model, history_matrix):
    model.history_matrix = history_matrix
    for attribute in ("primary", "fallback"):
        child = getattr(model, attribute, None)
        if child is not None:
            _attach_history(child, history_matrix)


def main() -> None:
    ensure_utf8_stdout()

    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", action="append",
                        help="Domain của bundle dữ liệu (lặp lại). Mặc định: tất cả -> 'multi_domain'; "
                             "1 domain -> bundle tên domain; tập con khác bị từ chối.")
    parser.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    args = parser.parse_args()

    model_cfg = load_config("eval/baselines")["baselines"]
    eval_cfg = load_config("eval/recommendation_metrics")
    ks = eval_cfg["recommendation_metrics"]["k_values"]
    sparse_max = load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"]
    model_names = [str(m).strip() for m in model_cfg["models"] if str(m).strip()]
    popularity_source = str(model_cfg.get("popularity_source", "train_core"))
    hybrid_weight = model_cfg.get("item_knn_hybrid_weight")
    paths = get_data_paths(domains=args.domain)
    splits_dir = str(paths.splits_dir)

    train, val, test = load_splits(splits_dir)
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
        model = build_model(name, model_cfg)
        t0 = time.time()

        if name == "item_knn" and core is not None:
            compact = build_core_model(paths, args.eval_on, int(model_cfg["item_knn"]["k"]),
                                       fit_df, user2id, item2id)
            primary = getattr(model, "primary", model)
            primary.train_matrix = training_matrix
            primary.num_users, primary.num_items = training_matrix.shape
            primary.similarity = compact.similarity.T.tocsr()
            if primary is not model:
                model.train_matrix = training_matrix
                model.num_users, model.num_items = training_matrix.shape
                model.fallback.fit(training_matrix)
        else:
            model.fit(fit_matrix if name == "popularity" and popularity_source == "full_history"
                      else training_matrix)
            if name == "popularity" and popularity_source == "full_history":
                model.name = "history_popularity"
                # Keep the same core-item metric buckets as the train-core runs.
                model.item_familiarity_matrix = training_matrix
        _attach_history(model, fit_matrix)

        if name == "item_knn" and hybrid_weight is not None:
            primary = getattr(model, "primary", model)
            model = HybridItemKNNRecommender(primary, fit_matrix, float(hybrid_weight))

        fit_seconds = time.time() - t0

        result = evaluate_recommender(model, fit_matrix, target_matrix, ks, sparse_max=sparse_max)
        all_metrics[model.name] = result.to_metrics(fit_seconds)
        fit_splits_by_model[model.name] = (
            (["train"] if args.eval_on == "validation" else ["train", "validation"])
            if name == "popularity" and popularity_source == "full_history"
            else (["train_core"] if core is not None
                  else (["train"] if args.eval_on == "validation" else ["train", "validation"])))

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
        next_experiment_dir(paths.output_dir("baselines")),
        config={"models": model_names, "ks": ks, "sparse_max": sparse_max, "baselines": model_cfg,
                "popularity_source": popularity_source,
                "item_knn_hybrid_weight": hybrid_weight,
                "hybrid_popularity_source": "full pre-target history" if hybrid_weight is not None else None,
                "item_familiarity_source": "train_core" if core is not None else "pre-target history",
                "fit_splits_by_model": fit_splits_by_model,
                "fit_splits": (["train_core"] if core is not None
                               else (["train"] if args.eval_on == "validation" else ["train", "validation"])),
                "population": "all target-bearing users; segments and exclusion use full pre-target history"},
        metrics=all_metrics,
        seed=model_cfg.get("seed", 42),
        dataset_info=dataset_info,
        runtime_seconds=time.time() - t_start,
    )
    print(f"saved experiment -> {exp_dir}")
    print("=== END REPORT ===")


if __name__ == "__main__":
    main()
