"""Phase 4: tune popularity and ItemKNN baselines, then report final test metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.evaluation.recommendation_metrics import evaluate_ranking
from src.recommenders.baselines import ItemKNNRecommender, PopularityRecommender


def _read_split(path: Path) -> pd.DataFrame:
    required = ["user_idx", "item_idx"]
    frame = pd.read_parquet(path, columns=required)
    if frame.empty:
        raise ValueError(f"Split is empty: {path}")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--splits-dir", default="data/splits/multi_domain")
    parser.add_argument("--output-dir", default="experiments/phase4_baselines")
    parser.add_argument("--k-values", default="5,10,20")
    parser.add_argument("--item-knn-neighbors", default="20,50")
    parser.add_argument("--skip-item-knn", action="store_true")
    args = parser.parse_args()
    k_values = sorted({int(value) for value in args.k_values.split(",")})
    candidates = sorted({int(value) for value in args.item_knn_neighbors.split(",")})

    splits_dir = Path(args.splits_dir)
    train, validation, test = (_read_split(splits_dir / name) for name in ("train.parquet", "validation.parquet", "test.parquet"))
    print(f"loaded train={len(train)} validation={len(validation)} test={len(test)}")
    results: dict[str, object] = {"k_values": k_values, "validation": {}, "test": {}}

    popularity = PopularityRecommender().fit(train)
    results["validation"]["popularity"] = evaluate_ranking(popularity, validation, k_values)
    popularity.fit(pd.concat([train, validation], ignore_index=True))
    results["test"]["popularity"] = evaluate_ranking(popularity, test, k_values)
    print("popularity complete")

    if not args.skip_item_knn:
        validation_runs: dict[int, dict[str, float]] = {}
        for neighbors in candidates:
            print(f"fitting ItemKNN neighbors={neighbors} (exact sparse co-occurrence; may need substantial RAM)")
            model = ItemKNNRecommender(neighbors).fit(train)
            validation_runs[neighbors] = evaluate_ranking(model, validation, k_values)
        selection_k = 10 if 10 in k_values else max(k_values)
        best = max(candidates, key=lambda value: validation_runs[value][f"ndcg@{selection_k}"])
        results["validation"]["item_knn"] = {"runs": validation_runs, "selected_neighbors": best}
        final_model = ItemKNNRecommender(best).fit(pd.concat([train, validation], ignore_index=True))
        results["test"]["item_knn"] = evaluate_ranking(final_model, test, k_values)
        print(f"item_knn complete selected_neighbors={best}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "metrics.json"
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"=== PHASE 4 DONE: metrics -> {output} ===")


if __name__ == "__main__":
    main()
