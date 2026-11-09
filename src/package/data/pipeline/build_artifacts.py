"""Stage 4: build corpus and ItemKNN artifacts for agent evaluation."""

from __future__ import annotations

import time

from ...config import DataPaths, load_config
from ...data import build_first_seen_timestamps
from ...data.split import load_splits
from ...data.mapping import load_mappings
from .._shared.select_fit_target import select_fit_target
from .build_meta_files import build_meta_files
from ...corpus import save_corpus
from ...corpus.build_corpus import build_corpus
from ...recommenders.runtime.item_knn_recommender import ItemKNNRecommender
from ...recommenders.shared.save_item_knn import save_item_knn


def build_artifacts(
    paths: DataPaths,
    domains: list[str] | None = None,
    eval_on: list[str] = ("validation", "test"),
    skip_corpus: bool = False,
    skip_item_knn: bool = False,
    force: bool = False,
) -> dict:
    """Build corpus and ItemKNN artifacts for agent evaluation.

    Args:
        paths: DataPaths configuration.
        domains: List of domain names. If None, uses all domains from config.
        eval_on: List of splits to build ItemKNN for ("validation", "test", or both).
        skip_corpus: Skip corpus building.
        skip_item_knn: Skip ItemKNN building.
        force: Overwrite existing output files.

    Returns:
        Report dictionary with statistics.

    Raises:
        FileExistsError: If output exists and force=False.
    """
    print(f"=== STAGE 4: build artifacts (tag={paths.tag}) ===")

    # Load configurations
    agent_cfg = load_config("agent/agent_eval")["agent_eval"]
    baselines_cfg = load_config("eval/baselines")["baselines"]
    min_coverage = float(agent_cfg["min_metadata_coverage"])
    min_coverage_by_domain = {
        str(domain): float(value)
        for domain, value in agent_cfg.get("min_metadata_coverage_by_domain", {}).items()
    }
    knn_k = int(baselines_cfg["item_knn"]["k"])

    # Check input dependencies
    if not paths.mapped_dir.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {paths.mapped_dir} — chạy python scripts/data_pipeline/run_pipeline.py --stages 3 trước."
        )

    # Load mappings
    user2id, item2id = load_mappings(paths.mapped_dir)
    print(f"loaded mappings: {len(user2id)} users, {len(item2id)} items")

    # Build meta_files
    meta_files = build_meta_files(paths, domains)
    print(f"meta_files: {len(meta_files)} domains")

    # Build corpus
    corpus_report = {}
    if not skip_corpus:
        corpus_path = paths.corpus_path
        if corpus_path.exists() and not force:
            raise FileExistsError(f"{corpus_path} đã tồn tại. Dùng --force để ghi đè.")

        print("Build corpus")
        first_seen_ts = build_first_seen_timestamps(
            [(domain, paths.cleaned_path(domain)) for domain, _ in meta_files]
        )
        corpus, meta, coverage, build_times = build_corpus(
            meta_files, item2id, min_coverage, timing=True, first_seen_ts=first_seen_ts,
            min_coverage_by_domain=min_coverage_by_domain,
        )
        print(f"Corpus: built in {sum(build_times.values()):.2f}s")

        duplicate_counts = meta.attrs.get("duplicates_dropped_by_domain", {})
        save_time = save_corpus(
            corpus, corpus_path, meta_files, item2id, min_coverage, coverage, build_times,
            coverage_by_domain=coverage.by_domain,
            duplicates_dropped_by_domain=duplicate_counts,
        )
        corpus_report = {
            "num_items": len(item2id),
            "coverage": coverage,
            "coverage_by_domain": coverage.by_domain,
            "metadata_duplicates_dropped_by_domain": duplicate_counts,
            "build_time": sum(build_times.values()),
            "save_time": save_time,
        }
    else:
        print("Skip corpus (skip_corpus=True)")

    # Build ItemKNN for each eval_on split
    item_knn_reports = {}
    if not skip_item_knn:
        # Load splits
        train, val, test = load_splits(paths.splits_dir, ("user_idx", "item_idx", "timestamp"))

        for split in eval_on:
            item_knn_path = paths.item_knn_path(split)
            if item_knn_path.exists() and not force:
                raise FileExistsError(f"{item_knn_path} đã tồn tại. Dùng --force để ghi đè.")

            # Select fit/target data
            if split == "validation":
                fit_df, _ = select_fit_target(train, val, test, "validation")
            elif split == "test":
                fit_df, _ = select_fit_target(train, val, test, "test")
            else:
                raise ValueError(f"Unknown eval_on: {split}")

            print(f"Fit ItemKNN for {split}")
            t0 = time.perf_counter()
            knn = ItemKNNRecommender(knn_k).fit(fit_df[["user_idx", "item_idx"]])
            fit_time = time.perf_counter() - t0
            knn._fit_time = fit_time
            print(f"ItemKNN: fitted in {fit_time:.1f}s")

            save_item_knn(knn, item_knn_path, knn_k, fit_df[["user_idx", "item_idx"]],
                          user2id=user2id, item2id=item2id, eval_on=split, tag=paths.tag)
            print(f"ItemKNN: saved to {item_knn_path}")

            item_knn_reports[split] = {
                "k": knn_k,
                "num_rows": len(fit_df),
                "fit_time": fit_time,
            }
    else:
        print("Skip ItemKNN (skip_item_knn=True)")

    print("=== STAGE 4 DONE ===")

    # Print summary
    print("\nArtifact paths:")
    if not skip_corpus:
        print(f"  corpus: {paths.corpus_path}")
    if not skip_item_knn:
        for split in eval_on:
            print(f"  item_knn ({split}): {paths.item_knn_path(split)}")

    print("\nTo use these artifacts:")
    print(f"  python scripts/evaluation/run_agent_eval.py")
    if len(eval_on) == 1:
        print(f"  (will use ItemKNN for {eval_on[0]})")
    else:
        print("  (will use ItemKNN for the specified --eval-on)")

    return {
        "corpus": corpus_report,
        "item_knn": item_knn_reports,
    }
