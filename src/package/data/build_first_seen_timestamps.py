"""Compute each namespaced item's earliest timestamp from cleaned interaction files."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from .domain import namespaced_item_id


def build_first_seen_timestamps(
    cleaned_files: list[tuple[str, str | Path]], *, batch_size: int = 250_000
) -> dict[str, int]:
    """Return min cleaned-event timestamp by namespaced item, using bounded row batches."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    first_seen: dict[str, int] = {}
    for domain, raw_path in cleaned_files:
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"cleaned interactions missing for first_seen_ts: {path}")
        parquet = pq.ParquetFile(path)
        missing = {"parent_asin", "timestamp"} - set(parquet.schema.names)
        if missing:
            raise ValueError(f"{path} is missing first_seen columns: {sorted(missing)}")
        for batch in parquet.iter_batches(columns=["parent_asin", "timestamp"], batch_size=batch_size):
            frame = batch.to_pandas()
            mins = frame.groupby("parent_asin", sort=False)["timestamp"].min()
            for item, timestamp in mins.items():
                key = namespaced_item_id(domain, str(item))
                value = int(timestamp)
                previous = first_seen.get(key)
                if previous is None or value < previous:
                    first_seen[key] = value
    return first_seen
