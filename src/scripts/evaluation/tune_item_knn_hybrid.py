"""Tune CF/popularity blending on disjoint validation cohorts; never read test rows."""
import argparse
import json
import time

import numpy as np
import pandas as pd

from package.config import get_data_paths, load_config
from package.data.mapping import load_mappings
from package.evaluation.recommender.experiment.next_experiment_dir import next_experiment_dir
from package.evaluation.recommender.experiment.save_experiment import save_experiment
from package.evaluation.recommender.analysis.build_core_model import build_core_model
from package.evaluation.recommender.analysis.core_inputs import core_inputs
from package.evaluation.recommender.analysis.global_core_pairs import global_core_pairs
from package.evaluation.recommender.core.evaluate_recommender import evaluate_recommender
from package.recommenders import build_interaction_matrix, ItemKNNMatrixRecommender, PopularityMatrixRecommender
from package.recommenders.evaluation.hybrid_item_knn_recommender import HybridItemKNNRecommender
from package.recommenders.shared import file_hash


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", action="append")
    ap.add_argument("--per-segment", type=int, default=3000, help="Users per segment per tuning/confirmation arm")
    ap.add_argument("--seed", type=int, default=20261103)
    ap.add_argument("--weights", default="0,0.25,0.5,1,2,4,8")
    ap.add_argument("--all-users", action="store_true", help="Evaluate all validation users with a previously chosen --weights value; no tuning")
    args = ap.parse_args()
    weights = [float(w) for w in args.weights.split(",")]
    if args.per_segment < 1 or not weights or any(not np.isfinite(w) or w < 0 for w in weights):
        ap.error("positive per-segment and finite nonnegative weights required")
    if args.all_users and len(weights) != 1:
        ap.error("--all-users requires exactly one previously selected weight")
    paths = get_data_paths(domains=args.domain)
    started = time.perf_counter()
    print("[load] train/validation and mappings; no test rows loaded", flush=True)
    train = pd.read_parquet(paths.split_path("train"), columns=["user_idx", "item_idx", "timestamp"])
    target = pd.read_parquet(paths.split_path("validation"), columns=["user_idx", "item_idx", "timestamp"])
    if train.timestamp.max() >= target.timestamp.min():
        raise ValueError("train must precede validation")
    users, items = load_mappings(paths.mapped_dir)
    shape = (len(users), len(items))
    history = build_interaction_matrix(train, *shape)
    targets = build_interaction_matrix(target, *shape)
    population = np.flatnonzero(np.diff(targets.indptr))
    sizes = np.diff(history.indptr)
    sparse_max = int(load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"])
    pools = {"cold": population[sizes[population] == 0],
             "sparse": population[(sizes[population] > 0) & (sizes[population] <= sparse_max)],
             "warm": population[sizes[population] > sparse_max]}
    rng = np.random.default_rng(args.seed)
    arms = {"tuning": [], "confirmation": []}
    for pool in pools.values():
        shuffled = rng.permutation(pool)
        count = min(args.per_segment, len(pool) // 2)
        if not count:
            raise ValueError("insufficient users for disjoint tuning/confirmation")
        arms["tuning"].extend(shuffled[:count].tolist())
        arms["confirmation"].extend(shuffled[count:2*count].tolist())
    if args.all_users:
        arms = {"full_validation": population.tolist()}
    k = int(load_config("eval/baselines")["baselines"]["item_knn"]["k"])
    compact = build_core_model(paths, "validation", k, train, users, items)
    if compact is None:
        raise ValueError("this experiment requires temporal_train_core")
    core = core_inputs(paths, users, items)
    core_matrix = build_interaction_matrix(global_core_pairs(core), *shape)
    cf = ItemKNNMatrixRecommender(k=k)
    cf.train_matrix, cf.history_matrix = core_matrix, history
    cf.num_users, cf.num_items = shape
    cf.similarity = compact.similarity.T.tocsr()
    del compact, core, users, items, train, target
    popularity = PopularityMatrixRecommender().fit(core_matrix)
    popularity.history_matrix = history
    models = {"original_item_knn": cf, "core_popularity": popularity,
              "history_popularity": HybridItemKNNRecommender(cf, history, popularity_only=True)}
    for weight in weights:
        model = HybridItemKNNRecommender(cf, history, weight)
        models[model.name] = model
    results = {}
    selected = None
    for arm, cohort in arms.items():
        results[arm] = {}
        for name, model in models.items():
            # Confirmation evaluates the fixed winner, plus all control baselines.
            if arm == "confirmation" and name.startswith("hybrid_") and name != selected:
                continue
            result = evaluate_recommender(model, history, targets, [5, 10, 20],
                                          sparse_max=sparse_max, progress_every=1000,
                                          evaluation_users=np.array(cohort, dtype=np.int64))
            results[arm][name] = result.to_metrics(0)
            print(f"[{arm}] {name}: recall@10={result.overall['recall@10']:.6f} ndcg@10={result.overall['ndcg@10']:.6f}", flush=True)
        if arm == "tuning":
            # Population-weighted segment means avoid optimizing an artificial
            # equal-segment pooled average dominated by the smaller warm cohort.
            def objective(name):
                rows = results[arm][name]["by_segment"]
                return sum(rows[s]["ndcg@10"] * len(pools[s]) for s in pools) / len(population)
            selected = max((n for n in models if n.startswith("hybrid_")), key=objective)
            print(f"[selected on tuning only] {selected}", flush=True)
    output = save_experiment(next_experiment_dir(paths.experiments_dir / "item_knn_hybrid"),
        config={"selected_on_tuning": selected, "objective": "population-weighted segment ndcg@10",
                "weights": weights, "cohorts": arms, "fit_splits": ["train_core"],
                "popularity_source": "full pre-validation train; binary unique user-item pairs",
                "cf_normalization": "per-user max before exclusion", "parameters": vars(args),
                "input_hashes": {name: file_hash(paths.split_path(name)) for name in ("train", "validation")},
                "stage3_sha256": file_hash(paths.splits_dir / "stage_3.manifest.json")},
        metrics=results, seed=args.seed, dataset_info={"tag": paths.tag, "eval_on": "validation",
                "population_users": len(population), "segment_population": {s: len(p) for s, p in pools.items()}},
        runtime_seconds=time.perf_counter()-started,
        notes="Validation development experiment. Confirmation users disjoint from tuning in this run; both belong to the previously inspected full validation split. No test quality evaluation. Baselines retain core-item familiarity denominators.")
    print(f"saved experiment -> {output}", flush=True)


if __name__ == "__main__":
    main()
