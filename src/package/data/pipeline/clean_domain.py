"""Stage 1: clean interactions for a single domain."""

from __future__ import annotations

import os
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
    chunk_size = chunk_size or load_config("data/cleaning")["cleaning"]["chunk_size"]

    if not review_path.exists():
        raise FileNotFoundError(f"Không tìm thấy {review_path} — tải review của '{domain}' về trước.")

    print(f"=== STAGE 1: clean domain={domain}, chunk_size={chunk_size} ===")

    output_path = paths.cleaned_path(domain)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        if not force:
            raise FileExistsError(f"{output_path} đã tồn tại. Dùng --force để chạy lại và ghi đè.")
        output_path.unlink()

    db_fd, db_name = tempfile.mkstemp(prefix="stage1_dedupe_", suffix=".sqlite", dir=output_dir)
    os.close(db_fd)
    tmp_output = output_path.with_name(output_path.name + ".tmp")
    report = {
        "num_input": 0,
        "num_dropped_missing_required_fields": 0,
        "num_dropped_duplicates": 0,
        "num_output": 0,
    }
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
            cleaned_chunk, chunk_report = clean_interactions(raw_chunk)
            report["num_input"] += chunk_report["num_input"]
            report["num_dropped_missing_required_fields"] += chunk_report[
                "num_dropped_missing_required_fields"
            ]
            report["num_dropped_duplicates"] += chunk_report["num_dropped_duplicates"]

            before_insert = connection.total_changes
            connection.executemany(
                "INSERT OR IGNORE INTO interactions VALUES (?, ?, ?, ?)",
                cleaned_chunk.itertuples(index=False, name=None),
            )
            inserted = connection.total_changes - before_insert
            report["num_dropped_duplicates"] += len(cleaned_chunk) - inserted
            report["num_output"] += inserted
            print(
                f"chunk={chunk_number} raw_rows={len(raw_chunk)} "
                f"clean_rows={len(cleaned_chunk)} inserted={inserted} "
                f"memory_mb={estimate_memory_usage_mb(raw_chunk):.1f}"
            )

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

    print(
        f"cleaned input={report['num_input']} "
        f"dropped_missing={report['num_dropped_missing_required_fields']} "
        f"dropped_duplicates={report['num_dropped_duplicates']} "
        f"output={report['num_output']}"
    )
    print(f"=== STAGE 1 DONE: saved {report['num_output']} rows -> {output_path} ===")

    return report
