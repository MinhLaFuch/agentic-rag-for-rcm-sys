"""Stage 2: merge domains and apply k-core filtering."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ...config import DataPaths, load_config
from .. import tag_domain
from ..clean import clean_interactions
from ..domain import domain_breakdown, merge_domains
from ..filter import k_core_filter
from ..loader import estimate_memory_usage_mb, optimize_interaction_dtypes
from ..manifest import check_upstream_manifests, pipeline_config_files, write_manifest
from ...config import PROJECT_ROOT


_OUTPUT_ROW_GROUP_SIZE = 250_000


def _write_filtered_parquet(
    frame: pd.DataFrame,
    output_path: Path,
    *,
    row_group_size: int = _OUTPUT_ROW_GROUP_SIZE,
) -> None:
    """Write bounded row groups without persisting frame-wide category vocabularies."""
    if row_group_size <= 0:
        raise ValueError("row_group_size must be positive")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".tmp")
    writer = None
    try:
        for start in range(0, len(frame), row_group_size):
            chunk = frame.iloc[start:start + row_group_size].copy(deep=False)
            for column in chunk.columns:
                if isinstance(chunk[column].dtype, pd.CategoricalDtype):
                    # Categorical columns produced during domain merging can carry
                    # millions of unused labels. Materialize only this chunk's values.
                    chunk[column] = chunk[column].astype(pd.StringDtype(storage="python"))
            table = pa.Table.from_pandas(chunk, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(temporary, table.schema, compression="snappy")
            writer.write_table(table, row_group_size=len(chunk))
        if writer is None:
            raise ValueError("cannot write an empty filtered interactions frame")
        writer.close()
        writer = None
        os.replace(temporary, output_path)
    except BaseException:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass
        temporary.unlink(missing_ok=True)
        raise


def merge_filter_domains(
    paths: DataPaths,
    domains: list[str],
    force: bool = False,
    cold_start_report: bool = False,
    allow_manifest_mismatch: bool = False,
    legacy_kcore_before_split: bool = True,
) -> dict:
    """Merge/deduplicate domains; optionally preserve legacy pre-split k-core.

    Args:
        paths: DataPaths configuration.
        domains: List of domain names to merge.
        force: Overwrite existing output.
        cold_start_report: Print cold-start statistics (expensive).

    Returns:
        Report dictionary with statistics.

    Raises:
        SystemExit: If k-core filtering removes all data (BLOCKED).
    """
    filtering_config = load_config("data/filtering")
    min_user = filtering_config["filtering"]["min_user_interactions"]
    min_item = filtering_config["filtering"]["min_item_interactions"]
    output_path = paths.filtered_path
    for domain in domains:
        cleaned_path = paths.cleaned_path(domain)
        if not cleaned_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy {cleaned_path}")
    upstream = [paths.stage1_manifest_path(domain) for domain in domains]
    identity_warnings = []
    for domain, manifest_path in zip(domains, upstream):
        if not manifest_path.is_file():
            continue
        manifest_tag = json.loads(manifest_path.read_text(encoding="utf-8")).get("tag")
        if manifest_tag != paths.tag:
            message = (
                f"Stage 1 manifest tag mismatch for {domain}: expected={paths.tag}, "
                f"actual={manifest_tag}; rerun Stage 1 for this tag"
            )
            if not allow_manifest_mismatch:
                raise ValueError(message)
            identity_warnings.append(message)
    manifest_warnings = check_upstream_manifests(upstream, [[paths.cleaned_path(domain)] for domain in domains],
                                                 allow_mismatch=allow_manifest_mismatch)
    manifest_warnings.extend(identity_warnings)

    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} đã tồn tại. Dùng --force để ghi đè.")

    print(f"=== STAGE 2: merge + filter domains={domains} tag={paths.tag} ===")

    tagged_dfs = []
    for domain in domains:
        path = paths.cleaned_path(domain)
        if not path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy {path} — chạy python scripts/data_pipeline/run_pipeline.py --stages 1 --domain {domain} trước."
            )
        df = pd.read_parquet(path)
        print(f"  loaded domain={domain} rows={len(df)} memory_mb={estimate_memory_usage_mb(df):.1f}")
        tagged_dfs.append(tag_domain(df, domain))

    merged = merge_domains(tagged_dfs)
    del tagged_dfs
    print(f"merged total_rows={len(merged)} memory_mb={estimate_memory_usage_mb(merged):.1f}")

    breakdown = domain_breakdown(merged)
    for _, row in breakdown.iterrows():
        print(
            f"  domain={row['domain']} interactions={row['num_interactions']} "
            f"users={row['num_users']} items={row['num_items']}"
        )

    # Preserve Stage 2's existing first-row-wins behavior; Stage 1 explicitly uses last-row-wins.
    merged, dedupe_report = clean_interactions(merged, duplicate_keep="first")
    print(f"post_merge_dedupe dropped={dedupe_report['num_dropped_duplicates']}")

    before_users = merged["user_id"].nunique()
    if legacy_kcore_before_split:
        filtered = k_core_filter(merged, min_user_interactions=min_user, min_item_interactions=min_item)
        print(
            f"legacy k_core_filter (min_user={min_user}, min_item={min_item}) "
            f"users_before={before_users} users_after={filtered['user_id'].nunique()} "
            f"rows_after={len(filtered)}"
        )
    else:
        filtered = merged
        print("temporal_train_core protocol: Stage 2 skips k-core; fitting filter runs on train in Stage 3")

    if cold_start_report and legacy_kcore_before_split:
        per_domain_warm = {}
        for domain in domains:
            single = merged[merged["domain"] == domain]
            single_filtered = k_core_filter(single, min_user_interactions=min_user, min_item_interactions=min_item)
            per_domain_warm[domain] = single_filtered["user_id"].nunique()
        print(
            f"cold_start_check per_domain_warm_users={per_domain_warm} "
            f"combined_warm_users={filtered['user_id'].nunique()}"
        )
    del merged

    if len(filtered) == 0:
        sys.exit(
            "BLOCKED: k-core filtering loại bỏ toàn bộ dữ liệu — giảm ngưỡng filtering trong configs/data/filtering.yaml. "
            "Nếu vẫn OOM: chạy ít domain cùng lúc với tag riêng (--domain D1 --domain D2 --tag mytag), "
            "hoặc tăng tạm filtering.min_user_interactions/min_item_interactions."
        )

    filtered = optimize_interaction_dtypes(filtered)
    _write_filtered_parquet(filtered, output_path)

    write_manifest(
        output_path.parent / "stage_2.manifest.json",
        project_root=PROJECT_ROOT,
        stage="merge_filter_domains",
        tag=paths.tag,
        inputs=[paths.cleaned_path(domain) for domain in domains],
        outputs=[output_path],
        config_files=pipeline_config_files("merge_filter_domains"),
        upstream_manifests=[path for path in upstream if path.is_file()],
        counts={"num_rows": int(len(filtered)), "num_users": int(filtered["user_id"].nunique()), "num_items": int(filtered["parent_asin"].nunique())},
        flags={"domains": domains, "min_user_interactions": int(min_user), "min_item_interactions": int(min_item), "force": bool(force), "cold_start_report": bool(cold_start_report), "legacy_kcore_before_split": bool(legacy_kcore_before_split)},
        warnings=manifest_warnings,
    )

    print(f"=== STAGE 2 DONE: saved {len(filtered)} rows -> {output_path} ===")

    return {"num_rows": len(filtered), "num_users": filtered["user_id"].nunique(), "num_items": filtered["parent_asin"].nunique()}
