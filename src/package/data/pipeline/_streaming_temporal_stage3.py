"""Out-of-core Stage 3 implementation for the fixed-cutoff train-core protocol."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ...config import DataPaths, PROJECT_ROOT
from ...data.mapping import ITEM2ID_FILE, USER2ID_FILE
from ...data.split.split_path import split_path
from ..manifest import pipeline_config_files, write_manifest


_BATCH_SIZE = 100_000


def _mapping_digest(connection: sqlite3.Connection, table: str) -> str:
    digest = hashlib.sha256()
    digest.update(b"[")
    first = True
    for key, index in connection.execute(f"SELECT key, id - 1 FROM {table} ORDER BY key COLLATE BINARY"):
        if not first:
            digest.update(b",")
        first = False
        digest.update(b"[")
        digest.update(json.dumps(str(key), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b",")
        digest.update(str(int(index)).encode("ascii"))
        digest.update(b"]")
    digest.update(b"]")
    return digest.hexdigest()


def _write_mapping(connection: sqlite3.Connection, table: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as output:
        output.write("{")
        first = True
        for key, index in connection.execute(f"SELECT key, id - 1 FROM {table} ORDER BY id"):
            if not first:
                output.write(",")
            first = False
            output.write(json.dumps(str(key), ensure_ascii=False))
            output.write(":")
            output.write(str(int(index)))
        output.write("}")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, target)


def _register_batch_values(
    connection: sqlite3.Connection, batch_table: str, mapping_table: str, values: list[str]
) -> None:
    unique = list(dict.fromkeys(values))
    connection.execute(f"DELETE FROM {batch_table}")
    connection.executemany(
        f"INSERT INTO {batch_table}(key, seq) VALUES (?, ?)",
        ((value, position) for position, value in enumerate(unique)),
    )
    connection.execute(
        f"INSERT INTO {mapping_table}(key) "
        f"SELECT b.key FROM {batch_table} AS b "
        f"LEFT JOIN {mapping_table} AS m ON m.key = b.key "
        "WHERE m.id IS NULL ORDER BY b.seq"
    )


def _batch_lookup(connection: sqlite3.Connection, batch_table: str, mapping_table: str,
                  values: list[str]) -> dict[str, int]:
    unique = list(dict.fromkeys(values))
    connection.execute(f"DELETE FROM {batch_table}")
    connection.executemany(
        f"INSERT INTO {batch_table}(key, seq) VALUES (?, ?)",
        ((value, position) for position, value in enumerate(unique)),
    )
    return {
        str(key): int(index) - 1
        for key, index in connection.execute(
            f"SELECT b.key, m.id FROM {batch_table} AS b "
            f"JOIN {mapping_table} AS m ON m.key = b.key"
        )
    }


def _batch_to_pandas(batch: pa.RecordBatch) -> pd.DataFrame:
    """Convert only values present in this batch, not file-wide dictionary categories."""
    arrays = [
        column.dictionary_decode() if pa.types.is_dictionary(field.type) else column
        for field, column in zip(batch.schema, batch.columns)
    ]
    decoded = pa.RecordBatch.from_arrays(arrays, names=batch.schema.names)
    # The source pandas metadata can mark dictionary columns as categorical. Once the
    # dictionary is decoded that metadata is stale and would re-create global categories.
    return decoded.to_pandas(ignore_metadata=True)


def _append_parquet(writers: dict[str, pq.ParquetWriter], paths: dict[str, Path],
                    name: str, frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    table = pa.Table.from_pandas(frame, preserve_index=False)
    if name not in writers:
        paths[name].parent.mkdir(parents=True, exist_ok=True)
        writers[name] = pq.ParquetWriter(paths[name], table.schema, compression="zstd")
    writers[name].write_table(table)


def _run_streaming_temporal_stage3(
    paths: DataPaths,
    *,
    cutoff_1: int,
    cutoff_2: int,
    min_user_pairs: int,
    min_item_pairs: int,
    sparse_max: int,
    scratch_dir: str | Path,
    force: bool,
    manifest_warnings: list[str],
    ratios: tuple[float, float, float],
) -> dict[str, Any]:
    """Split/map train-core data in bounded batches using a temporary SQLite index."""
    source = paths.filtered_path
    parquet = pq.ParquetFile(source)
    columns = parquet.schema_arrow.names
    required = {"user_id", "parent_asin", "timestamp", "domain", "rating"}
    if not required.issubset(columns):
        raise ValueError(f"Stage 2 parquet is missing columns required by streaming Stage 3: {sorted(required - set(columns))}")
    all_columns = columns
    temp_root = Path(scratch_dir)
    temp_root.mkdir(parents=True, exist_ok=True)
    if not temp_root.is_dir():
        raise NotADirectoryError(temp_root)

    split_outputs = {name: split_path(paths.splits_dir, name) for name in ("train", "validation", "test")}
    fit_core_path = paths.splits_dir / "train_core.parquet"
    cohort_path = paths.splits_dir / "evaluation_cohort.parquet"
    fit_mapping_dir = paths.mapped_dir / "fit_core"
    output_paths = [*split_outputs.values(), fit_core_path, cohort_path,
                    paths.mapped_dir / USER2ID_FILE, paths.mapped_dir / ITEM2ID_FILE,
                    fit_mapping_dir / USER2ID_FILE, fit_mapping_dir / ITEM2ID_FILE]
    if not force:
        existing = [str(path) for path in output_paths if path.exists()]
        if existing:
            raise FileExistsError("Stage 3 outputs exist (use --force): " + ", ".join(existing))

    with tempfile.TemporaryDirectory(prefix=f"{paths.tag}_stage3_", dir=temp_root) as temp_name:
        db_path = Path(temp_name) / "stage3.sqlite"
        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute("PRAGMA cache_size=-262144")
        connection.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE);
            CREATE TABLE items (id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE);
            CREATE TABLE batch_users (key TEXT PRIMARY KEY, seq INTEGER NOT NULL);
            CREATE TABLE batch_items (key TEXT PRIMARY KEY, seq INTEGER NOT NULL);
            CREATE TABLE train_pairs (
                user_idx INTEGER NOT NULL, item_idx INTEGER NOT NULL,
                PRIMARY KEY(user_idx, item_idx)
            ) WITHOUT ROWID;
            CREATE INDEX train_pairs_by_item ON train_pairs(item_idx, user_idx);
            CREATE TABLE train_users_domain(domain TEXT NOT NULL, user_idx INTEGER NOT NULL,
                PRIMARY KEY(domain,user_idx)) WITHOUT ROWID;
            CREATE TABLE train_items_domain(domain TEXT NOT NULL, item_idx INTEGER NOT NULL,
                PRIMARY KEY(domain,item_idx)) WITHOUT ROWID;
            CREATE TABLE train_items(item_idx INTEGER PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE target_events(split TEXT NOT NULL, domain TEXT NOT NULL,
                user_idx INTEGER NOT NULL, item_idx INTEGER NOT NULL);
            CREATE INDEX target_events_by_split_domain ON target_events(split,domain);
            CREATE TABLE fit_users(user_idx INTEGER PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE fit_items(item_idx INTEGER PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE next_users(user_idx INTEGER PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE next_items(item_idx INTEGER PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE batch_global_users(user_idx INTEGER PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE batch_global_items(item_idx INTEGER PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE fit_users_export(id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE);
            CREATE TABLE fit_items_export(id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE);
        """)
        try:
            rows_seen = 0
            pass_started = time.perf_counter()
            print("Stage 3 streaming pass 1/3: build disk-backed ID index")
            for batch in parquet.iter_batches(batch_size=_BATCH_SIZE, columns=["user_id", "parent_asin"]):
                users = ["" if value is None else str(value) for value in batch.column("user_id").to_pylist()]
                items = ["" if value is None else str(value) for value in batch.column("parent_asin").to_pylist()]
                if "" in users or "" in items:
                    raise ValueError("Stage 2 input contains empty user_id or parent_asin")
                _register_batch_values(connection, "batch_users", "users", users)
                _register_batch_values(connection, "batch_items", "items", items)
                rows_seen += batch.num_rows
                if rows_seen and rows_seen % 2_000_000 < batch.num_rows:
                    elapsed = max(time.perf_counter() - pass_started, 1e-9)
                    print(f"  indexed_rows={rows_seen:,}/{parquet.metadata.num_rows:,} speed={rows_seen / elapsed:,.0f} rows/s eta={(parquet.metadata.num_rows - rows_seen) / (rows_seen / elapsed):.0f}s users={connection.execute('SELECT COUNT(*) FROM users').fetchone()[0]:,} items={connection.execute('SELECT COUNT(*) FROM items').fetchone()[0]:,}", flush=True)
                connection.commit()
            n_users = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
            n_items = int(connection.execute("SELECT COUNT(*) FROM items").fetchone()[0])
            if rows_seen == 0:
                raise ValueError("Stage 2 input is empty")

            print("Stage 3 streaming pass 2/3: write fixed-cutoff splits and train-pair index")
            pass_started = time.perf_counter()
            rows_processed = 0
            temp_split_paths = {name: path.with_name(path.name + ".tmp") for name, path in split_outputs.items()}
            writers: dict[str, pq.ParquetWriter] = {}
            split_rows = {name: 0 for name in split_outputs}
            train_rows_by_domain: dict[str, int] = {}
            split_min = {name: None for name in split_outputs}
            split_max = {name: None for name in split_outputs}
            for batch in parquet.iter_batches(batch_size=_BATCH_SIZE, columns=all_columns):
                rows_processed += batch.num_rows
                frame = _batch_to_pandas(batch)
                user_values = frame["user_id"].astype(str).tolist()
                item_values = frame["parent_asin"].astype(str).tolist()
                user_map = _batch_lookup(connection, "batch_users", "users", user_values)
                item_map = _batch_lookup(connection, "batch_items", "items", item_values)
                frame["user_idx"] = frame["user_id"].astype(str).map(user_map).astype("int64")
                frame["item_idx"] = frame["parent_asin"].astype(str).map(item_map).astype("int64")
                timestamps = pd.to_numeric(frame["timestamp"], errors="raise").astype("int64")
                selectors = {
                    "train": timestamps <= cutoff_1,
                    "validation": (timestamps > cutoff_1) & (timestamps <= cutoff_2),
                    "test": timestamps > cutoff_2,
                }
                for split_name, mask in selectors.items():
                    selected = frame.loc[mask]
                    if selected.empty:
                        continue
                    values = selected["timestamp"]
                    minimum, maximum = int(values.min()), int(values.max())
                    split_min[split_name] = minimum if split_min[split_name] is None else min(split_min[split_name], minimum)
                    split_max[split_name] = maximum if split_max[split_name] is None else max(split_max[split_name], maximum)
                    split_rows[split_name] += len(selected)
                    _append_parquet(writers, temp_split_paths, split_name, selected)
                    if split_name == "train":
                        train_rows_by_domain.update({key: train_rows_by_domain.get(key, 0) + int(value)
                                                     for key, value in selected.groupby("domain", observed=True).size().items()})
                        pairs = selected[["user_idx", "item_idx"]].drop_duplicates()
                        connection.executemany("INSERT OR IGNORE INTO train_pairs VALUES (?, ?)", pairs.itertuples(index=False, name=None))
                        for domain, group in selected.groupby("domain", observed=True):
                            users_for_domain = group["user_idx"].drop_duplicates().tolist()
                            items_for_domain = group["item_idx"].drop_duplicates().tolist()
                            connection.executemany("INSERT OR IGNORE INTO train_users_domain VALUES (?, ?)", ((str(domain), int(value)) for value in users_for_domain))
                            connection.executemany("INSERT OR IGNORE INTO train_items_domain VALUES (?, ?)", ((str(domain), int(value)) for value in items_for_domain))
                            connection.executemany("INSERT OR IGNORE INTO train_items VALUES (?)", ((int(value),) for value in items_for_domain))
                    else:
                        connection.executemany(
                            "INSERT INTO target_events VALUES (?, ?, ?, ?)",
                            ((split_name, str(domain), int(user_idx), int(item_idx))
                             for domain, user_idx, item_idx in selected[["domain", "user_idx", "item_idx"]].itertuples(index=False, name=None)),
                        )
                connection.commit()
                if rows_processed and rows_processed % 2_000_000 < batch.num_rows:
                    elapsed = max(time.perf_counter() - pass_started, 1e-9)
                    speed = rows_processed / elapsed
                    print(f"  split_rows={rows_processed:,}/{parquet.metadata.num_rows:,} speed={speed:,.0f} rows/s eta={(parquet.metadata.num_rows - rows_processed) / speed:.0f}s train/val/test={split_rows}", flush=True)
            for writer in writers.values():
                writer.close()
            if any(split_rows[name] == 0 for name in split_rows):
                raise ValueError(f"Temporal split produced an empty partition: {split_rows}")
            if (split_max["train"] > cutoff_1 or split_min["validation"] <= cutoff_1
                    or split_max["validation"] > cutoff_2 or split_min["test"] <= cutoff_2):
                raise ValueError(
                    "Streaming temporal split failed cutoff validation: "
                    f"train_max={split_max['train']}, validation_min/max="
                    f"{split_min['validation']}/{split_max['validation']}, test_min={split_min['test']}"
                )
            for name, temporary in temp_split_paths.items():
                if not temporary.exists():
                    raise ValueError(f"Temporal split produced no rows for {name}")
                os.replace(temporary, split_outputs[name])

            print("Stage 3 streaming pass 3/3: fit-core, cohorts, and reports")
            connection.execute("INSERT INTO fit_users SELECT DISTINCT user_idx FROM train_pairs")
            connection.execute("INSERT INTO fit_items SELECT DISTINCT item_idx FROM train_pairs")
            connection.commit()
            core_iterations = 0
            core_started = time.perf_counter()
            for core_iterations in range(1, 21):
                connection.execute("DELETE FROM next_users")
                connection.execute("DELETE FROM next_items")
                active_join = "FROM train_pairs p JOIN fit_users u USING(user_idx) JOIN fit_items i USING(item_idx)"
                connection.execute(
                    "INSERT INTO next_users "
                    "SELECT p.user_idx " + active_join +
                    " GROUP BY p.user_idx HAVING COUNT(*) >= ?", (int(min_user_pairs),)
                )
                connection.execute(
                    "INSERT INTO next_items "
                    "SELECT p.item_idx " + active_join +
                    " GROUP BY p.item_idx HAVING COUNT(*) >= ?", (int(min_item_pairs),)
                )
                old_counts = (connection.execute("SELECT COUNT(*) FROM fit_users").fetchone()[0],
                              connection.execute("SELECT COUNT(*) FROM fit_items").fetchone()[0])
                new_counts = (connection.execute("SELECT COUNT(*) FROM next_users").fetchone()[0],
                              connection.execute("SELECT COUNT(*) FROM next_items").fetchone()[0])
                connection.execute("DELETE FROM fit_users")
                connection.execute("INSERT INTO fit_users SELECT user_idx FROM next_users")
                connection.execute("DELETE FROM fit_items")
                connection.execute("INSERT INTO fit_items SELECT item_idx FROM next_items")
                connection.commit()
                print(f"  fit_core_iteration={core_iterations} users={new_counts[0]:,} items={new_counts[1]:,} elapsed={time.perf_counter() - core_started:.1f}s", flush=True)
                if old_counts == new_counts:
                    break
            else:
                raise RuntimeError("train-core filtering did not converge within 20 iterations")

            fit_user_count = int(connection.execute("SELECT COUNT(*) FROM fit_users").fetchone()[0])
            fit_item_count = int(connection.execute("SELECT COUNT(*) FROM fit_items").fetchone()[0])
            # Dense local fit IDs use the lexicographically sorted raw IDs, as in prepare_train_core.
            connection.execute("CREATE TABLE fit_user_ids (user_idx INTEGER PRIMARY KEY, fit_idx INTEGER NOT NULL)")
            connection.execute("CREATE TABLE fit_item_ids (item_idx INTEGER PRIMARY KEY, fit_idx INTEGER NOT NULL)")
            connection.execute("""INSERT INTO fit_user_ids
                SELECT f.user_idx, ROW_NUMBER() OVER (ORDER BY u.key COLLATE BINARY) - 1
                FROM fit_users f JOIN users u ON u.id = f.user_idx + 1""")
            connection.execute("""INSERT INTO fit_item_ids
                SELECT f.item_idx, ROW_NUMBER() OVER (ORDER BY i.key COLLATE BINARY) - 1
                FROM fit_items f JOIN items i ON i.id = f.item_idx + 1""")
            connection.execute("""INSERT INTO fit_users_export
                SELECT x.fit_idx + 1, u.key FROM fit_user_ids x
                JOIN users u ON u.id=x.user_idx+1 ORDER BY x.fit_idx""")
            connection.execute("""INSERT INTO fit_items_export
                SELECT x.fit_idx + 1, i.key FROM fit_item_ids x
                JOIN items i ON i.id=x.item_idx+1 ORDER BY x.fit_idx""")
            connection.commit()
            active_user = bytearray(n_users)
            active_item = bytearray(n_items)
            for (idx,) in connection.execute("SELECT user_idx FROM fit_users"):
                active_user[int(idx)] = 1
            for (idx,) in connection.execute("SELECT item_idx FROM fit_items"):
                active_item[int(idx)] = 1

            # Export full and fit-only mappings incrementally; never materialize whole maps in RAM.
            global_user_path = paths.mapped_dir / USER2ID_FILE
            global_item_path = paths.mapped_dir / ITEM2ID_FILE
            fit_user_path = fit_mapping_dir / USER2ID_FILE
            fit_item_path = fit_mapping_dir / ITEM2ID_FILE
            for target in (global_user_path, global_item_path, fit_user_path, fit_item_path):
                target.parent.mkdir(parents=True, exist_ok=True)
            _write_mapping(connection, "users", global_user_path)
            _write_mapping(connection, "items", global_item_path)
            _write_mapping(connection, "fit_users_export", fit_user_path)
            _write_mapping(connection, "fit_items_export", fit_item_path)

            train_core_temp = fit_core_path.with_name(fit_core_path.name + ".tmp")
            core_writer = None
            core_rows = 0
            core_rows_by_domain: dict[str, int] = {}
            train_parquet = pq.ParquetFile(split_outputs["train"])
            for batch in train_parquet.iter_batches(batch_size=_BATCH_SIZE):
                frame = _batch_to_pandas(batch)
                keep = [bool(active_user[int(uid)] and active_item[int(iid)])
                        for uid, iid in zip(frame["user_idx"], frame["item_idx"])]
                if not any(keep):
                    continue
                core = frame.loc[keep].copy()
                for batch_table, fit_table, column in (
                    ("batch_global_users", "fit_user_ids", "user_idx"),
                    ("batch_global_items", "fit_item_ids", "item_idx"),
                ):
                    unique_ids = [int(value) for value in core[column].drop_duplicates().tolist()]
                    connection.execute(f"DELETE FROM {batch_table}")
                    connection.executemany(f"INSERT INTO {batch_table} VALUES (?)", ((value,) for value in unique_ids))
                    fit_lookup = {
                        int(global_id): int(fit_id)
                        for global_id, fit_id in connection.execute(
                            f"SELECT b.{column}, f.fit_idx FROM {batch_table} b "
                            f"JOIN {fit_table} f ON f.{column}=b.{column}"
                        )
                    }
                    core[column] = core[column].map(fit_lookup).astype("int64")
                table = pa.Table.from_pandas(core, preserve_index=False)
                if core_writer is None:
                    core_writer = pq.ParquetWriter(train_core_temp, table.schema, compression="zstd")
                core_writer.write_table(table)
                core_rows += len(core)
                for domain, group in core.groupby("domain", observed=True):
                    key = str(domain)
                    core_rows_by_domain[key] = core_rows_by_domain.get(key, 0) + len(group)
            if core_writer is not None:
                core_writer.close()
            else:
                raise ValueError("train-core is empty after filtering")
            os.replace(train_core_temp, fit_core_path)

            # Cohorts use unique user-item pairs in chronological train.
            connection.execute("CREATE TABLE train_history(user_idx INTEGER PRIMARY KEY, history_size INTEGER NOT NULL)")
            connection.execute("INSERT INTO train_history SELECT user_idx, COUNT(*) FROM train_pairs GROUP BY user_idx")
            connection.commit()
            cohort_temp = cohort_path.with_name(cohort_path.name + ".tmp")
            cohort_writer = None
            cohort_sizes: dict[str, int] = {}
            for eval_split in ("validation", "test"):
                query = """SELECT DISTINCT m.key AS user_id,
                    COALESCE(h.history_size, 0) AS history_size,
                    CASE WHEN COALESCE(h.history_size, 0)=0 THEN 'cold'
                         WHEN h.history_size<=? THEN 'sparse' ELSE 'warm' END AS segment,
                    ? AS eval_on
                    FROM target_events t JOIN users m ON m.id=t.user_idx+1
                    LEFT JOIN train_history h ON h.user_idx=t.user_idx
                    WHERE t.split=? ORDER BY m.key COLLATE BINARY"""
                cursor = connection.execute(query, (int(sparse_max), eval_split, eval_split))
                while rows := cursor.fetchmany(50_000):
                    frame = pd.DataFrame.from_records(rows, columns=["user_id", "history_size", "segment", "eval_on"])
                    cohort_sizes[eval_split] = cohort_sizes.get(eval_split, 0) + len(frame)
                    table = pa.Table.from_pandas(frame, preserve_index=False)
                    if cohort_writer is None:
                        cohort_writer = pq.ParquetWriter(cohort_temp, table.schema, compression="zstd")
                    cohort_writer.write_table(table)
            if cohort_writer is not None:
                cohort_writer.close()
                os.replace(cohort_temp, cohort_path)
            else:
                raise ValueError("No target-bearing users found for evaluation cohort")

            print("=== TEMPORAL TRAIN-CORE REPORT (per domain) ===")
            for (domain, users_before) in connection.execute(
                "SELECT domain, COUNT(*) FROM train_users_domain GROUP BY domain ORDER BY domain"
            ):
                items_before = int(connection.execute("SELECT COUNT(*) FROM train_items_domain WHERE domain=?", (domain,)).fetchone()[0])
                users_after = int(connection.execute("""SELECT COUNT(DISTINCT p.user_idx) FROM train_pairs p
                    JOIN fit_users u USING(user_idx) JOIN fit_items i USING(item_idx)
                    JOIN items it ON it.id=p.item_idx+1 WHERE substr(it.key,1,instr(it.key,'::')-1)=?""", (domain,)).fetchone()[0])
                items_after = int(connection.execute("""SELECT COUNT(DISTINCT p.item_idx) FROM train_pairs p
                    JOIN fit_users u USING(user_idx) JOIN fit_items i USING(item_idx)
                    JOIN items it ON it.id=p.item_idx+1 WHERE substr(it.key,1,instr(it.key,'::')-1)=?""", (domain,)).fetchone()[0])
                print(f"{domain}: train events/users/items {train_rows_by_domain.get(domain, 0)}/{users_before}/{items_before} -> fit-core events/users/items {core_rows_by_domain.get(domain, 0)}/{users_after}/{items_after}")
                for eval_split in ("validation", "test"):
                    stats = connection.execute("""SELECT COUNT(*), COUNT(DISTINCT t.user_idx),
                        COUNT(DISTINCT CASE WHEN h.user_idx IS NULL THEN t.user_idx END),
                        COUNT(DISTINCT CASE WHEN ti.item_idx IS NULL THEN t.item_idx END),
                        SUM(CASE WHEN ti.item_idx IS NULL THEN 1 ELSE 0 END)
                        FROM target_events t LEFT JOIN train_history h ON h.user_idx=t.user_idx
                        LEFT JOIN train_items ti ON ti.item_idx=t.item_idx
                        WHERE t.split=? AND t.domain=?""", (eval_split, domain)).fetchone()
                    target_events, target_users, no_history, cold_items, cold_event_count = map(int, stats)
                    rate = cold_event_count / target_events if target_events else 0.0
                    print(f"  {eval_split}: target_events={target_events} users_without_train_history={no_history}; target_items_absent_from_train={cold_items}; cold-item target-event rate={cold_event_count}/{target_events} ({rate:.4%})")
            print(f"validation cohort users={cohort_sizes.get('validation', 0):,}; test cohort users={cohort_sizes.get('test', 0):,}")
            print("=== END REPORT ===")

            mapping_hashes = {
                global_user_path: _mapping_digest(connection, "users"),
                global_item_path: _mapping_digest(connection, "items"),
                fit_user_path: _mapping_digest(connection, "fit_users_export"),
                fit_item_path: _mapping_digest(connection, "fit_items_export"),
            }
            outputs = [global_user_path, global_item_path, *split_outputs.values(), fit_core_path, cohort_path, fit_user_path, fit_item_path]
            write_manifest(
                paths.splits_dir / "stage_3.manifest.json", project_root=PROJECT_ROOT,
                stage="map_split", tag=paths.tag, inputs=[source], outputs=outputs,
                config_files=pipeline_config_files("map_split"),
                upstream_manifests=[paths.filtered_path.parent / "stage_2.manifest.json"],
                counts={"num_users": n_users, "num_items": n_items,
                        "train_rows": split_rows["train"], "validation_rows": split_rows["validation"],
                        "test_rows": split_rows["test"], "fit_core_rows": core_rows},
                flags={"force": bool(force), "data_protocol": "temporal_train_core",
                       "cutoff_1": int(cutoff_1), "cutoff_2": int(cutoff_2),
                       "split_assignment": "train<=cutoff_1; validation<=cutoff_2; test>cutoff_2",
                       "train_ratio": ratios[0], "validation_ratio": ratios[1], "test_ratio": ratios[2],
                       "mapping_strategy": "first_occurrence_disk_backed_sqlite",
                       "fit_core_counts": "unique_train_user_item_pairs",
                       "fit_core_min_user_pairs": int(min_user_pairs),
                       "fit_core_min_item_pairs": int(min_item_pairs),
                       "fit_core_max_iterations": 20,
                       "sparse_max_history": int(sparse_max),
                       "streaming_batch_rows": _BATCH_SIZE},
                warnings=manifest_warnings, mapping_hash_overrides=mapping_hashes,
            )
            print(f"Stage 3 streaming complete: users={n_users:,} items={n_items:,} splits={split_rows}; fit_core={core_rows:,}")
            return {"num_users": n_users, "num_items": n_items, "train_rows": split_rows["train"],
                    "val_rows": split_rows["validation"], "test_rows": split_rows["test"],
                    "fit_core": {"rows_before": split_rows["train"], "rows_after": core_rows,
                                 "users_after": fit_user_count, "items_after": fit_item_count,
                                 "fit_core_path": str(fit_core_path), "fit_mapping_dir": str(fit_mapping_dir),
                                 "cohort_path": str(cohort_path)}}
        finally:
            connection.close()
