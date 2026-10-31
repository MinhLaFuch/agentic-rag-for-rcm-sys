"""Stage 1: clean interactions for a single domain."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ...config import DataPaths, load_config
from ..clean import clean_interactions, iter_reviews_dataframes
from ..loader import estimate_memory_usage_mb
from ..manifest import pipeline_config_files, write_manifest
from ...config import PROJECT_ROOT


def clean_domain(
    paths: DataPaths,
    domain: str,
    review_path: Path | None = None,
    output_dir: Path | None = None,
    chunk_size: int | None = None,
    force: bool = False,
) -> dict:
    """Clean interactions for a single domain.

    Args:
        paths: DataPaths configuration.
        domain: Domain name.
        review_path: Override path to review file (default: paths.review_path(domain)).
        output_dir: Override output directory (default: paths.cleaned_dir).
        chunk_size: Number of reviews to process per chunk (default: config).
        force: Overwrite existing output.

    Returns:
        Report dictionary with statistics.
    """
    if output_dir:
        paths = replace(paths, cleaned_dir=Path(output_dir))
    review_path = Path(review_path) if review_path else paths.review_path(domain)
    cleaning_cfg = load_config("data/cleaning")["cleaning"]
    chunk_size = chunk_size or cleaning_cfg["chunk_size"]

    if not review_path.exists():
        raise FileNotFoundError(f"Không tìm thấy {review_path} — tải review của '{domain}' về trước.")

    print(f"=== STAGE 1: clean domain={domain}, chunk_size={chunk_size} ===")

    output_path = paths.cleaned_path(domain)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        if not force:
            raise FileExistsError(f"{output_path} đã tồn tại. Dùng --force để chạy lại và ghi đè.")

    db_fd, db_name = tempfile.mkstemp(prefix="stage1_dedupe_", suffix=".sqlite", dir=output_dir)
    os.close(db_fd)
    tmp_output = output_path.with_name(output_path.name + ".tmp")
    report = {
        "num_input": 0,
        "num_dropped_missing_required_fields": 0,
        "num_dropped_invalid_rating": 0,
        "num_dropped_invalid_timestamp": 0,
        "num_dropped_duplicates": 0,
        "num_output": 0,
        "num_user_timestamp_multiple_items": 0,
        "num_events_in_user_timestamp_multi_item_groups": 0,
        "num_consecutive_same_user_item": 0,
    }
    previous_key = None
    connection = sqlite3.connect(db_name)

    try:
        connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            CREATE TABLE interactions (
                user_id TEXT NOT NULL,
                parent_asin TEXT NOT NULL,
                rating REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                PRIMARY KEY (user_id, parent_asin, timestamp)
            ) WITHOUT ROWID;
            CREATE TABLE observed_user_timestamp_items (
                user_id TEXT NOT NULL, timestamp INTEGER NOT NULL, parent_asin TEXT NOT NULL,
                PRIMARY KEY (user_id, timestamp, parent_asin)
            ) WITHOUT ROWID;
            """
        )

        for chunk_number, raw_chunk in enumerate(
            iter_reviews_dataframes(
                review_path,
                columns=["user_id", "parent_asin", "rating", "timestamp"],
                chunksize=chunk_size,
            ),
            start=1,
        ):
            if str(raw_chunk["user_id"].dtype) != "string" or str(raw_chunk["parent_asin"].dtype) != "string":
                raise TypeError("Stage 1 requires user_id and parent_asin to be read as pandas string dtype")
            # Source-order diagnostic; carry the boundary across chunks.
            keys = [
                (None if pd.isna(user) else str(user), None if pd.isna(item) else str(item))
                for user, item in zip(raw_chunk["user_id"].tolist(), raw_chunk["parent_asin"].tolist())
            ]
            if keys:
                report["num_consecutive_same_user_item"] += sum(
                    1 for left, right in zip(([previous_key] if previous_key is not None else []) + keys[:-1], keys)
                    if left == right and right[0] is not None and right[1] is not None
                )
                previous_key = keys[-1]

            cleaned_chunk, chunk_report = clean_interactions(
                raw_chunk,
                validate_values=True,
                min_timestamp_ms=int(cleaning_cfg["min_timestamp_ms"]),
                max_timestamp_ms=int(cleaning_cfg["max_timestamp_ms"]),
                # Enforce the configured rate over the whole source, not per chunk.
                max_invalid_timestamp_fraction=1.0,
                duplicate_keep="last",
            )
            report["num_input"] += chunk_report["num_input"]
            report["num_dropped_missing_required_fields"] += chunk_report[
                "num_dropped_missing_required_fields"
            ]
            report["num_dropped_invalid_rating"] += chunk_report["num_dropped_invalid_rating"]
            report["num_dropped_invalid_timestamp"] += chunk_report["num_dropped_invalid_timestamp"]

            connection.executemany(
                "INSERT OR IGNORE INTO observed_user_timestamp_items VALUES (?, ?, ?)",
                cleaned_chunk[["user_id", "timestamp", "parent_asin"]].itertuples(index=False, name=None),
            )
            connection.executemany(
                "INSERT INTO interactions VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, parent_asin, timestamp) DO UPDATE SET rating=excluded.rating",
                cleaned_chunk.itertuples(index=False, name=None),
            )
            print(
                f"chunk={chunk_number} raw_rows={len(raw_chunk)} clean_rows={len(cleaned_chunk)} "
                f"upserted={len(cleaned_chunk)} "
                f"memory_mb={estimate_memory_usage_mb(raw_chunk):.1f}"
            )

        report["num_output"] = int(connection.execute("SELECT COUNT(*) FROM interactions").fetchone()[0])
        report["num_dropped_duplicates"] = (
            report["num_input"] - report["num_dropped_missing_required_fields"]
            - report["num_dropped_invalid_rating"] - report["num_dropped_invalid_timestamp"]
            - report["num_output"]
        )
        report["num_user_timestamp_multiple_items"] = int(connection.execute(
            "SELECT COUNT(*) FROM (SELECT user_id, timestamp FROM observed_user_timestamp_items "
            "GROUP BY user_id, timestamp HAVING COUNT(*) > 1)"
        ).fetchone()[0])
        report["num_events_in_user_timestamp_multi_item_groups"] = int(connection.execute(
            "SELECT COUNT(*) FROM observed_user_timestamp_items AS observed "
            "WHERE EXISTS (SELECT 1 FROM observed_user_timestamp_items AS peer "
            "WHERE peer.user_id=observed.user_id AND peer.timestamp=observed.timestamp "
            "AND peer.parent_asin<>observed.parent_asin)"
        ).fetchone()[0])
        invalid_ts_fraction = report["num_dropped_invalid_timestamp"] / max(1, report["num_input"])
        if invalid_ts_fraction > float(cleaning_cfg["max_invalid_timestamp_fraction"]):
            raise ValueError(
                f"Invalid timestamp rows {report['num_dropped_invalid_timestamp']}/{report['num_input']} "
                f"({invalid_ts_fraction:.2%}) exceed configured maximum "
                f"{float(cleaning_cfg['max_invalid_timestamp_fraction']):.2%}; "
                "possibly incorrect timestamp unit (expected milliseconds)."
            )
        report["num_users"] = connection.execute("SELECT COUNT(DISTINCT user_id) FROM interactions").fetchone()[0]
        report["num_items"] = connection.execute("SELECT COUNT(DISTINCT parent_asin) FROM interactions").fetchone()[0]
        writer: pq.ParquetWriter | None = None
        try:
            for output_chunk in pd.read_sql_query(
                "SELECT user_id, parent_asin, rating, timestamp FROM interactions",
                connection,
                chunksize=chunk_size,
            ):
                output_chunk["rating"] = output_chunk["rating"].astype("float32")
                table = pa.Table.from_pandas(output_chunk, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(tmp_output, table.schema, compression="snappy")
                writer.write_table(table)
            if writer is None:
                pd.DataFrame(columns=["user_id", "parent_asin", "rating", "timestamp"]).to_parquet(
                    tmp_output, index=False
                )
        finally:
            if writer is not None:
                writer.close()
    finally:
        connection.close()
        Path(db_name).unlink(missing_ok=True)

    os.replace(tmp_output, output_path)

    scoped_manifest = paths.stage1_manifest_path(domain, tag_scoped=True)
    write_manifest(
        scoped_manifest,
        project_root=PROJECT_ROOT,
        stage="clean_domain",
        tag=paths.tag,
        inputs=[review_path],
        outputs=[output_path],
        config_files=pipeline_config_files("clean_domain"),
        counts={key: int(value) for key, value in report.items()},
        flags={"domain": domain, "chunk_size": int(chunk_size), "force": bool(force),
               "duplicate_policy": "keep_last_valid_row_by_source_order",
               "timestamp_unit": "milliseconds",
               "timestamp_range": [int(cleaning_cfg["min_timestamp_ms"]), int(cleaning_cfg["max_timestamp_ms"])],
               "max_invalid_timestamp_fraction": float(cleaning_cfg["max_invalid_timestamp_fraction"])},
    )
    # Keep the first legacy shared manifest intact for old chains. Replacing it here
    # would invalidate an existing Stage 2 manifest that recorded its hash.
    shared_manifest = output_path.parent / "stage_1.manifest.json"
    if not shared_manifest.exists():
        shared_fd, shared_temp_name = tempfile.mkstemp(
            prefix="stage_1_manifest_", suffix=".tmp", dir=shared_manifest.parent
        )
        os.close(shared_fd)
        shared_temp = Path(shared_temp_name)
        try:
            shutil.copyfile(scoped_manifest, shared_temp)
            try:
                # Create the compatibility alias only if another run has not won the race.
                os.link(shared_temp, shared_manifest)
            except FileExistsError:
                pass
        finally:
            shared_temp.unlink(missing_ok=True)

    print(
        f"cleaned input={report['num_input']} "
        f"dropped_missing={report['num_dropped_missing_required_fields']} "
        f"dropped_invalid_rating={report['num_dropped_invalid_rating']} "
        f"dropped_invalid_timestamp={report['num_dropped_invalid_timestamp']} "
        f"dropped_duplicates={report['num_dropped_duplicates']} "
        f"same_user_timestamp_multi_item={report['num_user_timestamp_multiple_items']} "
        f"affected_events={report['num_events_in_user_timestamp_multi_item_groups']} "
        f"consecutive_same_user_item={report['num_consecutive_same_user_item']} "
        f"output={report['num_output']}"
    )
    print(f"=== STAGE 1 DONE: saved {report['num_output']} rows -> {output_path} ===")

    return report
