"""Validation-only Phase 4 tuning, with an optional one-time final test run.

Example:
    PYTHONPATH=. python scripts/py/tune_baselines.py
    PYTHONPATH=. python scripts/py/tune_baselines.py --tag vg_toys --run-final-test
"""

from __future__ import annotations

import argparse
import time

import pandas as pd

from package.config import get_data_paths, load_config
from package.data.split import infer_matrix_shape, load_splits
from package.tools.evaluation.evaluator import EvaluationResult, evaluate_recommender
from package.tools.evaluation.experiment_log import next_experiment_dir, save_experiment
from package.tools.evaluation.tuning import merge_model_params, parameter_grid
from package.tools.recommenders import build_interaction_matrix, build_model
from package.utils.console import ensure_utf8_stdout


def _serialize_result(result: EvaluationResult, fit_seconds: float) -> dict:
    return {
        "overall": result.overall,
        "by_segment": result.by_segment,
        "num_users": result.num_users,
        "catalog_coverage": result.catalog_coverage,
        "target_item_seen_ratio": result.target_item_seen_ratio,
        "fit_seconds": round(fit_seconds, 2),
    }


def main() -> None:
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Tên lần chạy (mặc định: run_tag trong data.yaml).")
    parser.add_argument("--splits-dir", help="Mặc định: <splits_dir>/<tag> trong data.yaml.")
    parser.add_argument("--models", help="Mặc định: tuning.models trong model.yaml.")
    parser.add_argument("--ks", default=None)
    parser.add_argument("--selection-metric", default=None, help="Mặc định lấy tuning.selection_metric")
    parser.add_argument("--run-final-test", action="store_true", help="Refit cấu hình thắng với train+validation rồi đánh giá test một lần.")
    parser.add_argument("--experiments-dir", default="experiments")
    args = parser.parse_args()

    model_config = load_config("model")
    base_config = model_config["baselines"]
    tuning_config = model_config["tuning"]
    evaluation_config = load_config("evaluation")
    ks = [int(value) for value in args.ks.split(",")] if args.ks else evaluation_config["recommendation_metrics"]["k_values"]
    metric = args.selection_metric or tuning_config["selection_metric"]
    if metric not in {f"{name}@{k}" for name in ("precision", "recall", "hit_rate", "ndcg", "mrr", "map") for k in ks}:
        raise ValueError(f"selection metric '{metric}' is not available for ks={ks}")
    sparse_max = evaluation_config["segment_thresholds"]["sparse_max_history"]
    model_names = args.models.split(",") if args.models else tuning_config["models"]
    model_names = [name.strip() for name in model_names if name.strip()]
    allowed = {"popularity", "item_knn", "bpr_mf"}
    unknown = set(model_names) - allowed
    if unknown:
        raise ValueError(f"Tuning supports only {sorted(allowed)}, got {sorted(unknown)}")

    splits_dir = args.splits_dir or str(get_data_paths(args.tag).splits_dir)
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
            trial = {"model": model.name, "base_model": model_name, "params": params, "metrics": _serialize_result(result, time.time() - fit_start)}
            trials.append(trial)
            score = result.overall[metric]
            print(f"model={model.name} params={params} {metric}={score:.6f}")
            if best is None or score > best["metrics"]["overall"][metric]:
                best = trial

    assert best is not None
    metrics: dict = {"selection_metric": metric, "validation_trials": trials, "selected": best}
    dataset_info = {
        "splits_dir": splits_dir,
        "num_users": num_users,
        "num_items": num_items,
        "train_interactions": int(train_matrix.nnz),
        "validation_interactions": int(validation_matrix.nnz),
        "final_test_ran": args.run_final_test,
    }

    if args.run_final_test:
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
            "metrics": _serialize_result(final_result, time.time() - fit_start),
        }
        dataset_info["final_fit_interactions"] = int(fit_matrix.nnz)
        dataset_info["test_interactions"] = int(test_matrix.nnz)
        print(f"FINAL model={final_model.name} {metric}={final_result.overall[metric]:.6f}")
    else:
        print("Validation tuning done. Re-run with --run-final-test only after reviewing the selected model.")

    output = save_experiment(
        next_experiment_dir(args.experiments_dir),
        config={"ks": ks, "sparse_max": sparse_max, "baselines": base_config, "tuning": tuning_config},
        metrics=metrics,
        seed=base_config["seed"],
        dataset_info=dataset_info,
        runtime_seconds=time.time() - start,
        notes="Hyperparameters were selected exclusively on validation. Test is present only when --run-final-test was explicitly requested.",
    )
    print(f"saved experiment -> {output}")


if __name__ == "__main__":
    main()
