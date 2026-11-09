"""Validation-only Phase 4 tuning, with an optional one-time final test run.

Example:
    PYTHONPATH=. python scripts/evaluation/tune_baselines.py
    PYTHONPATH=. python scripts/evaluation/tune_baselines.py --domain Video_Games

Mọi tham số đọc từ configs/eval/tuning.yaml, baselines.yaml, recommendation_metrics.yaml
và output dir từ data_paths.yaml — không có override flag. Đánh giá test một lần
chỉ chạy khi tuning.run_final_test: true trong YAML.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from package.config import get_data_paths, load_config
from package.data.split import infer_matrix_shape, load_splits
from package.evaluation.recommender.core import evaluate_recommender
from package.evaluation.recommender.experiment import next_experiment_dir, save_experiment
from package.evaluation.recommender.config import merge_model_params, parameter_grid
from package.recommenders.shared import build_interaction_matrix, build_model
from package.utils import ensure_utf8_stdout


def main() -> None:
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", action="append",
                        help="Domain của bundle dữ liệu (lặp lại). Mặc định: tất cả -> 'multi_domain'; "
                             "1 domain -> bundle tên domain; tập con khác bị từ chối.")
    args = parser.parse_args()

    base_config = load_config("eval/baselines")["baselines"]
    tuning_config = load_config("eval/tuning")["tuning"]
    recommendation_metrics = load_config("eval/recommendation_metrics")
    ks = recommendation_metrics["recommendation_metrics"]["k_values"]
    metric = tuning_config["selection_metric"]
    if metric not in {f"{name}@{k}" for name in ("precision", "recall", "hit_rate", "ndcg", "mrr", "map") for k in ks}:
        raise ValueError(f"selection metric '{metric}' is not available for ks={ks}")
    sparse_max = load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"]
    model_names = [str(name).strip() for name in tuning_config["models"] if str(name).strip()]
    allowed = {"popularity", "item_knn", "bpr_mf"}
    unknown = set(model_names) - allowed
    if unknown:
        raise ValueError(f"Tuning supports only {sorted(allowed)}, got {sorted(unknown)}")

    paths = get_data_paths(domains=args.domain)
    splits_dir = str(paths.splits_dir)
    run_final_test = bool(tuning_config.get("run_final_test", False))
    train, validation, test = load_splits(splits_dir)
    num_users, num_items = infer_matrix_shape(train, validation, test)
    train_matrix = build_interaction_matrix(train, num_users, num_items)
    validation_matrix = build_interaction_matrix(validation, num_users, num_items)
    print(f"=== PHASE 4 TUNING (selection={metric}) ===")
    print(f"train_interactions={train_matrix.nnz} validation_interactions={validation_matrix.nnz}")

    start = time.time()
    trials: list[dict] = []
    best: dict | None = None
    for model_name in model_names:
        candidates = [{}] if model_name == "popularity" else parameter_grid(tuning_config[model_name])
        for params in candidates:
            config = merge_model_params(base_config, model_name, params)
            model = build_model(model_name, config)
            fit_start = time.time()
            model.fit(train_matrix)
            result = evaluate_recommender(model, train_matrix, validation_matrix, ks, sparse_max=sparse_max)
            trial = {"model": model.name, "base_model": model_name, "params": params, "metrics": result.to_metrics(time.time() - fit_start)}
            trials.append(trial)
            score = result.overall[metric]
            print(f"model={model.name} params={params} {metric}={score:.6f}")
            if best is None or score > best["metrics"]["overall"][metric]:
                best = trial

    assert best is not None
    metrics: dict = {"selection_metric": metric, "validation_trials": trials, "selected": best}
    dataset_info = {
        "tag": paths.tag,
        "splits_dir": splits_dir,
        "num_users": num_users,
        "num_items": num_items,
        "train_interactions": int(train_matrix.nnz),
        "validation_interactions": int(validation_matrix.nnz),
        "final_test_ran": run_final_test,
        "split_files": {
            name: {"path": str(Path(splits_dir) / f"{name}.parquet"),
                   "size_bytes": (Path(splits_dir) / f"{name}.parquet").stat().st_size,
                   "mtime_ns": (Path(splits_dir) / f"{name}.parquet").stat().st_mtime_ns}
            for name in ("train", "validation", "test")
        },
    }

    if run_final_test:
        print("=" * 70)
        print("WARNING: tuning.run_final_test is TRUE — the test split will be")
        print("evaluated ONCE for the selected model. Do not tune against it again.")
        print("=" * 70)
        fit_frame = pd.concat([train, validation], ignore_index=True)
        fit_matrix = build_interaction_matrix(fit_frame, num_users, num_items)
        test_matrix = build_interaction_matrix(test, num_users, num_items)
        config = merge_model_params(base_config, best["base_model"], best["params"])
        final_model = build_model(best["base_model"], config)
        fit_start = time.time()
        final_model.fit(fit_matrix)
        final_result = evaluate_recommender(final_model, fit_matrix, test_matrix, ks, sparse_max=sparse_max)
        metrics["final_test"] = {
            "model": final_model.name,
            "params": best["params"],
            "metrics": final_result.to_metrics(time.time() - fit_start),
        }
        dataset_info["final_fit_interactions"] = int(fit_matrix.nnz)
        dataset_info["test_interactions"] = int(test_matrix.nnz)
        print(f"FINAL model={final_model.name} {metric}={final_result.overall[metric]:.6f}")
    else:
        print("Validation tuning done. Set tuning.run_final_test: true in configs/eval/tuning.yaml to evaluate test once.")

    output = save_experiment(
        next_experiment_dir(paths.output_dir("baselines")),
        config={"ks": ks, "sparse_max": sparse_max, "baselines": base_config, "tuning": tuning_config},
        metrics=metrics,
        seed=base_config["seed"],
        dataset_info=dataset_info,
        runtime_seconds=time.time() - start,
        notes="Hyperparameters were selected exclusively on validation. Test is present only when tuning.run_final_test was enabled in YAML.",
    )
    print(f"saved experiment -> {output}")


if __name__ == "__main__":
    main()
