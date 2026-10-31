"""Stage 4: build corpus and ItemKNN artifacts for agent evaluation."""

from __future__ import annotations

import time
import json
from pathlib import Path

import pandas as pd

from ...config import DataPaths, load_config
from ...data import build_first_seen_timestamps
from ...data.split import load_splits
from ...data.mapping import load_mappings
from ...tools.evaluation import select_fit_target
from .build_meta_files import build_meta_files
from ...tools.corpus import save_corpus
from ...tools.corpus.build_corpus import build_corpus
from ...tools.recommenders import ItemKNNRecommender
from ...tools.recommenders.save_item_knn import save_item_knn
from ..manifest import check_upstream_manifests, pipeline_config_files, write_manifest
from ...config import PROJECT_ROOT
from ...data.mapping import ITEM2ID_FILE, USER2ID_FILE
from ...data.split.split_path import split_path


def build_artifacts(
    paths: DataPaths,
    domains: list[str] | None = None,
    eval_on: list[str] = ("validation", "test"),
    skip_corpus: bool = False,
    skip_item_knn: bool = False,
    force: bool = False,
    allow_manifest_mismatch: bool = False,
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
    upstream = [paths.splits_dir / "stage_3.manifest.json"]
    stage3_inputs = [paths.mapped_dir / USER2ID_FILE, paths.mapped_dir / ITEM2ID_FILE]
    fit_mapping_dir = paths.mapped_dir / "fit_core"
    fit_core_path = paths.splits_dir / "train_core.parquet"
    stage3_manifest = upstream[0]
    stage3_protocol = (json.loads(stage3_manifest.read_text(encoding="utf-8")).get("flags", {}).get("data_protocol")
                       if stage3_manifest.is_file() else None)
    use_train_core = stage3_protocol == "temporal_train_core"
    if use_train_core and not (fit_core_path.is_file() and
                               (fit_mapping_dir / USER2ID_FILE).is_file() and
                               (fit_mapping_dir / ITEM2ID_FILE).is_file()):
        raise FileNotFoundError("Stage 3 manifest declares temporal_train_core but fit-core artifacts are incomplete")
    if use_train_core:
        stage3_inputs += [fit_core_path, fit_mapping_dir / USER2ID_FILE, fit_mapping_dir / ITEM2ID_FILE]
    if not skip_item_knn:
        stage3_inputs += [split_path(paths.splits_dir, name) for name in ("train", "validation", "test")]

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
            f"Không tìm thấy {paths.mapped_dir} — chạy python scripts/data_pipeline/run_pipeline.py --stages 3 --tag {paths.tag} trước."
        )

    if not skip_corpus and paths.corpus_path.exists() and not force:
        raise FileExistsError(f"{paths.corpus_path} already exists; use force to overwrite")
    if not skip_item_knn:
        for split in eval_on:
            if paths.item_knn_path(split).exists() and not force:
                raise FileExistsError(f"{paths.item_knn_path(split)} already exists; use force to overwrite")
    manifest_warnings = check_upstream_manifests(upstream, [stage3_inputs], allow_mismatch=allow_manifest_mismatch)

    # The temporal protocol can contain tens of millions of evaluation users.
    # Stage 4 only needs their count; ItemKNN uses fit-only mappings and the
    # corpus needs the full item map. Avoid loading the unused global user map.
    if use_train_core:
        with (paths.mapped_dir / ITEM2ID_FILE).open("r", encoding="utf-8") as source:
            item2id = json.load(source)
        stage3_counts = json.loads(stage3_manifest.read_text(encoding="utf-8")).get("counts", {})
        num_users = int(stage3_counts.get("num_users", 0))
        fit_user2id, fit_item2id = load_mappings(fit_mapping_dir)
    else:
        user2id, item2id = load_mappings(paths.mapped_dir)
        num_users = len(user2id)
        fit_user2id, fit_item2id = user2id, item2id
    print(f"loaded mappings: {num_users} users, {len(item2id)} items")
    if use_train_core:
        print(f"temporal_train_core: ItemKNN fit uses {fit_core_path} and fit-only mappings")

    # Build meta_files
    meta_files = build_meta_files(paths, domains)
    print(f"meta_files: {len(meta_files)} domains")
    first_seen_ts = (
        build_first_seen_timestamps([(domain, paths.cleaned_path(domain)) for domain, _ in meta_files])
        if not skip_corpus else None
    )

    # Build corpus
    corpus_report = {}
    if not skip_corpus:
        corpus_path = paths.corpus_path
        if corpus_path.exists() and not force:
            raise FileExistsError(f"{corpus_path} đã tồn tại. Dùng --force để ghi đè.")

        print("Build corpus")
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
        train_core = (pd.read_parquet(fit_core_path) if use_train_core else None)

        for split in eval_on:
            item_knn_path = paths.item_knn_path(split)
            if item_knn_path.exists() and not force:
                raise FileExistsError(f"{item_knn_path} đã tồn tại. Dùng --force để ghi đè.")

            # Select fit/target data
            if use_train_core:
                fit_df = train_core[["user_idx", "item_idx"]]
            elif split == "validation":
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
                          user2id=fit_user2id, item2id=fit_item2id, eval_on=split, tag=paths.tag,
                          fit_splits=["train_core"] if use_train_core else None)
            print(f"ItemKNN: saved to {item_knn_path}")

            item_knn_reports[split] = {
                "k": knn_k,
                "num_rows": len(fit_df),
                "fit_time": fit_time,
            }
    else:
        print("Skip ItemKNN (skip_item_knn=True)")

    stage_inputs = [paths.mapped_dir / USER2ID_FILE, paths.mapped_dir / ITEM2ID_FILE]
    if use_train_core:
        stage_inputs += [fit_core_path, fit_mapping_dir / USER2ID_FILE, fit_mapping_dir / ITEM2ID_FILE]
    if not skip_item_knn:
        stage_inputs += [split_path(paths.splits_dir, name) for name in ("train", "validation", "test")]
    if not skip_corpus:
        stage_inputs += [path for _, raw_path in meta_files if (path := Path(raw_path)).is_file()]
        stage_inputs += [paths.cleaned_path(domain) for domain, _ in meta_files]
    stage_outputs = []
    if not skip_corpus:
        stage_outputs.extend([paths.corpus_path, paths.corpus_path.with_suffix(".meta.json")])
    if not skip_item_knn:
        for split in eval_on:
            item_knn_path = paths.item_knn_path(split)
            stage_outputs.extend([item_knn_path, item_knn_path.with_suffix(".meta.json")])
    split_rows = None
    if upstream[0].is_file():
        previous_counts = json.loads(upstream[0].read_text(encoding="utf-8")).get("counts", {})
        row_keys = ("train_rows", "validation_rows", "test_rows")
        if all(key in previous_counts for key in row_keys):
            split_rows = sum(int(previous_counts[key]) for key in row_keys)
    write_manifest(
        paths.corpus_dir / "stage_4.manifest.json",
        project_root=PROJECT_ROOT,
        stage="build_artifacts",
        tag=paths.tag,
        inputs=stage_inputs,
        outputs=stage_outputs,
        config_files=pipeline_config_files("build_artifacts"),
        upstream_manifests=[path for path in upstream if path.is_file()],
        counts={"num_rows": split_rows, "num_users": int(num_users), "num_items": int(len(item2id)),
                "num_metadata_sources": len(meta_files),
                "metadata_coverage_by_domain": corpus_report.get("coverage_by_domain", {}),
                "metadata_duplicates_dropped_by_domain": corpus_report.get("metadata_duplicates_dropped_by_domain", {})},
        flags={"domains": domains, "eval_on": eval_on, "skip_corpus": bool(skip_corpus), "skip_item_knn": bool(skip_item_knn), "force": bool(force), "item_knn_k": int(knn_k)},
        warnings=manifest_warnings,
    )

    print("=== STAGE 4 DONE ===")

    # Print summary
    print("\nArtifact paths:")
    if not skip_corpus:
        print(f"  corpus: {paths.corpus_path}")
    if not skip_item_knn:
        for split in eval_on:
            print(f"  item_knn ({split}): {paths.item_knn_path(split)}")

    print("\nTo use these artifacts:")
    print(f"  python scripts/evaluation/run_agent_eval.py --tag {paths.tag}")
    if len(eval_on) == 1:
        print(f"  (will use ItemKNN for {eval_on[0]})")
    else:
        print("  (will use ItemKNN for the specified --eval-on)")

    return {
        "corpus": corpus_report,
        "item_knn": item_knn_reports,
    }
