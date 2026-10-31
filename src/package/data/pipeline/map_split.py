"""Stage 3: ID mapping, temporal split, and leakage checks."""

from __future__ import annotations

import pandas as pd
import json

from ...config import DataPaths, load_config
from ..leakage import (
    check_no_duplicate_across_splits,
    check_profile_snapshot,
    check_split_temporal_order,
    check_fit_core_subset,
)
from ..mapping import apply_id_mapping, build_id_mappings, save_mappings
from ..split import compute_temporal_cutoffs, save_splits, temporal_split
from ..manifest import check_upstream_manifests, pipeline_config_files, write_manifest
from ...config import PROJECT_ROOT
from ...data.mapping import ITEM2ID_FILE, USER2ID_FILE
from ...data.split.split_path import split_path
from .prepare_train_core import prepare_train_core
from .build_evaluation_cohort import build_evaluation_cohort
from ._streaming_temporal_stage3 import _run_streaming_temporal_stage3


def map_split(paths: DataPaths, force: bool = False, allow_manifest_mismatch: bool = False,
              data_protocol: str = "legacy_kcore_before_split",
              scratch_dir: str | None = None) -> dict:
    """Apply ID mapping, temporal split, and leakage checks.

    Args:
        paths: DataPaths configuration.
        force: Overwrite existing splits.

    Returns:
        Report dictionary with statistics.
    """
    split_config = load_config("data/split")
    train_ratio = split_config["split"]["train_ratio"]
    val_ratio = split_config["split"]["validation_ratio"]
    test_ratio = split_config["split"]["test_ratio"]

    print(f"=== STAGE 3: ID mapping + temporal split + leakage check (tag={paths.tag}) ===")
    upstream = [paths.filtered_path.parent / "stage_2.manifest.json"]
    manifest_warnings = check_upstream_manifests(upstream, [[paths.filtered_path]], allow_mismatch=allow_manifest_mismatch)
    if upstream[0].is_file():
        stage2_flags = json.loads(upstream[0].read_text(encoding="utf-8")).get("flags", {})
        stage2_legacy = stage2_flags.get("legacy_kcore_before_split")
        expected_legacy = data_protocol == "legacy_kcore_before_split"
        if stage2_legacy is not None and bool(stage2_legacy) != expected_legacy:
            raise ValueError(
                f"Stage 2/3 data protocol mismatch for tag={paths.tag}: "
                f"stage_2 legacy_kcore_before_split={stage2_legacy}, stage_3 data_protocol={data_protocol}"
            )
        if data_protocol == "temporal_train_core" and stage2_legacy is None:
            raise ValueError("temporal_train_core requires a Stage 2 manifest created by the opt-in protocol")

    if not paths.filtered_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {paths.filtered_path} — chạy python scripts/data_pipeline/run_pipeline.py --stages 2 --tag {paths.tag} trước."
        )
    if paths.split_path("train").exists() and not force:
        raise FileExistsError(f"{paths.splits_dir} đã có splits. Dùng --force để ghi đè.")

    if data_protocol == "temporal_train_core":
        cutoff_cfg = split_config["split"]["temporal_train_core"]
        cutoff_1 = int(cutoff_cfg["train_end_inclusive_ms"])
        cutoff_2 = int(cutoff_cfg["validation_end_inclusive_ms"])
        if cutoff_1 >= cutoff_2:
            raise ValueError("temporal_train_core cutoffs must be strictly increasing")
        filtering_cfg = load_config("data/filtering")["filtering"]
        thresholds = load_config("eval/segment_thresholds")["segment_thresholds"]
        return _run_streaming_temporal_stage3(
            paths,
            cutoff_1=cutoff_1,
            cutoff_2=cutoff_2,
            min_user_pairs=int(filtering_cfg["min_user_interactions"]),
            min_item_pairs=int(filtering_cfg["min_item_interactions"]),
            sparse_max=int(thresholds["sparse_max_history"]),
            scratch_dir=scratch_dir or (paths.splits_dir / ".scratch"),
            force=force,
            manifest_warnings=manifest_warnings,
            ratios=(float(train_ratio), float(val_ratio), float(test_ratio)),
        )

    df = pd.read_parquet(paths.filtered_path)
    print(f"loaded rows={len(df)} users={df['user_id'].nunique()} items={df['parent_asin'].nunique()}")

    user2id, item2id = build_id_mappings(df)
    df = apply_id_mapping(df, user2id, item2id)
    print(f"id_mapping num_users={len(user2id)} num_items={len(item2id)}")

    save_mappings(user2id, item2id, paths.mapped_dir)
    print(f"saved mappings -> {paths.mapped_dir}")

    if data_protocol == "temporal_train_core":
        cutoff_cfg = split_config["split"]["temporal_train_core"]
        cutoff_1 = int(cutoff_cfg["train_end_inclusive_ms"])
        cutoff_2 = int(cutoff_cfg["validation_end_inclusive_ms"])
        if cutoff_1 >= cutoff_2:
            raise ValueError("temporal_train_core cutoffs must be strictly increasing")
    elif data_protocol == "legacy_kcore_before_split":
        cutoff_1, cutoff_2 = compute_temporal_cutoffs(df, train_ratio, val_ratio, test_ratio)
    else:
        raise ValueError(f"Unknown data_protocol: {data_protocol}")
    train, validation, test = temporal_split(df, cutoff_1, cutoff_2)
    print(
        f"temporal_split cutoff_1={cutoff_1} cutoff_2={cutoff_2} "
        f"train={len(train)} val={len(validation)} test={len(test)}"
    )

    check_split_temporal_order(train, validation, test)
    check_no_duplicate_across_splits(train, validation, test)
    check_profile_snapshot(as_of_timestamp=cutoff_1, source_interactions=train)
    print("leakage_check status=PASS (3/3 temporal/split checks)")

    fit_core_path = paths.splits_dir / "train_core.parquet"
    cohort_path = paths.splits_dir / "evaluation_cohort.parquet"
    fit_mapping_dir = paths.mapped_dir / "fit_core"
    fit_core_report = {}
    fit_user2id, fit_item2id = {}, {}
    if data_protocol == "temporal_train_core":
        filtering_cfg = load_config("data/filtering")["filtering"]
        prepared = prepare_train_core(train, filtering_cfg["min_user_interactions"], filtering_cfg["min_item_interactions"])
        train_core = prepared.core
        check_fit_core_subset(train, train_core)
        fit_user2id, fit_item2id = prepared.user2id, prepared.item2id
        fit_core_path.parent.mkdir(parents=True, exist_ok=True)
        train_core.to_parquet(fit_core_path, index=False)
        save_mappings(fit_user2id, fit_item2id, fit_mapping_dir)

        thresholds = load_config("eval/segment_thresholds")["segment_thresholds"]
        sparse_max = int(thresholds["sparse_max_history"])
        validation_cohort = build_evaluation_cohort(train, validation, sparse_max)
        validation_cohort["eval_on"] = "validation"
        test_cohort = build_evaluation_cohort(train, test, sparse_max)
        test_cohort["eval_on"] = "test"
        cohort = pd.concat([validation_cohort, test_cohort], ignore_index=True)
        cohort.to_parquet(cohort_path, index=False)

        print("=== TEMPORAL TRAIN-CORE REPORT (per domain) ===")
        for domain in sorted(set(df["domain"].astype(str))):
            train_d = train[train.domain == domain]
            core_d = train_core[train_core.domain == domain]
            train_users = set(train_d.user_id)
            train_items = set(train_d.parent_asin)
            print(
                f"{domain}: train events/users/items {len(train_d)}/{train_d.user_id.nunique()}/{train_d.parent_asin.nunique()} "
                f"-> fit-core events/users/items {len(core_d)}/{core_d.user_id.nunique()}/{core_d.parent_asin.nunique()}"
            )
            for split_name, target_d in (("validation", validation), ("test", test)):
                target_d = target_d[target_d.domain == domain]
                no_history_users = target_d.loc[~target_d.user_id.isin(train_users), "user_id"].nunique()
                cold_item_events = int((~target_d.parent_asin.isin(train_items)).sum())
                unique_target_items = target_d.parent_asin.nunique()
                cold_target_items = target_d.loc[~target_d.parent_asin.isin(train_items), "parent_asin"].nunique()
                print(
                    f"  {split_name}: target_events={len(target_d)} users_without_train_history={no_history_users}; "
                    f"target_items_absent_from_train={cold_target_items}/{unique_target_items}; "
                    f"cold-item target-event rate={cold_item_events}/{len(target_d)} "
                    f"({cold_item_events / len(target_d) if len(target_d) else 0:.4%})"
                )
        print(f"validation cohort users={len(validation_cohort)} segments={validation_cohort.segment.value_counts().to_dict()}")
        print(f"test cohort users={len(test_cohort)} segments={test_cohort.segment.value_counts().to_dict()}")
        print("=== END REPORT ===")
        fit_core_report = {
            "rows_before": len(train), "rows_after": len(train_core),
            "users_before": prepared.users_before, "items_before": prepared.items_before,
            "users_after": len(fit_user2id), "items_after": len(fit_item2id),
            "fit_core_path": str(fit_core_path), "fit_mapping_dir": str(fit_mapping_dir),
            "cohort_path": str(cohort_path),
        }

    save_splits(train, validation, test, paths.splits_dir)

    outputs = [paths.mapped_dir / USER2ID_FILE, paths.mapped_dir / ITEM2ID_FILE]
    outputs += [split_path(paths.splits_dir, name) for name in ("train", "validation", "test")]
    if data_protocol == "temporal_train_core":
        outputs += [fit_core_path, cohort_path, fit_mapping_dir / USER2ID_FILE, fit_mapping_dir / ITEM2ID_FILE]
    write_manifest(
        paths.splits_dir / "stage_3.manifest.json",
        project_root=PROJECT_ROOT,
        stage="map_split",
        tag=paths.tag,
        inputs=[paths.filtered_path],
        outputs=outputs,
        config_files=pipeline_config_files("map_split"),
        upstream_manifests=[path for path in upstream if path.is_file()],
        counts={"num_users": int(len(user2id)), "num_items": int(len(item2id)), "train_rows": int(len(train)), "validation_rows": int(len(validation)), "test_rows": int(len(test)), "fit_core_rows": int(fit_core_report.get("rows_after", 0))},
        flags={"force": bool(force), "data_protocol": data_protocol, "cutoff_1": int(cutoff_1), "cutoff_2": int(cutoff_2), "train_ratio": float(train_ratio), "validation_ratio": float(val_ratio), "test_ratio": float(test_ratio)},
        warnings=manifest_warnings,
    )

    print(f"=== STAGE 3 DONE: saved splits -> {paths.splits_dir} ===")

    return {
        "num_users": len(user2id),
        "num_items": len(item2id),
        "train_rows": len(train),
        "val_rows": len(validation),
        "test_rows": len(test),
        "fit_core": fit_core_report,
    }
