import argparse
import os
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from package.config import get_data_paths, load_config
from package.data.clean import clean_interactions, iter_reviews_dataframes
from package.data.loader import estimate_memory_usage_mb


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True)
    parser.add_argument("--review-path", help="Mặc định: <raw_dir>/<domain>.jsonl.gz trong data_paths.yaml")
    parser.add_argument("--output-dir", help="Mặc định: cleaned_dir trong data_paths.yaml")
    parser.add_argument(
        "--chunk-size",
        type=int,
        help="Số review đọc và xử lý mỗi lần (mặc định: cleaning.chunk_size trong cleaning.yaml).",
    )
    parser.add_argument("--force", action="store_true", help="Xóa output cũ (nếu có) và chạy lại.")
    args = parser.parse_args()

    if args.chunk_size is not None and args.chunk_size <= 0:
        parser.error("--chunk-size phải là số nguyên dương")

    paths = get_data_paths()
    review_path = Path(args.review_path) if args.review_path else paths.review_path(args.domain)
    chunk_size = args.chunk_size or load_config("cleaning")["cleaning"]["chunk_size"]
    if not review_path.exists():
        raise FileNotFoundError(f"Không tìm thấy {review_path} — tải review của '{args.domain}' về trước.")

    print(f"=== STAGE 1: clean domain={args.domain}, chunk_size={chunk_size} ===")

    output_root = Path(args.output_dir) if args.output_dir else paths.cleaned_dir
    output_dir = output_root / args.domain
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "interactions.parquet"
    if output_path.exists():
        if not args.force:
            raise FileExistsError(f"{output_path} đã tồn tại. Dùng --force để chạy lại và ghi đè.")
        output_path.unlink()

    db_fd, db_name = tempfile.mkstemp(prefix="stage1_dedupe_", suffix=".sqlite", dir=output_dir)
    os.close(db_fd)
    tmp_output = output_dir / "interactions.parquet.tmp"
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


if __name__ == "__main__":
    main()
