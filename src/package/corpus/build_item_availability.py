"""Extract item availability timestamps (avail_ts) from raw metadata JSONL(.gz)."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

_DATE_FORMATS = (
    "%B %d, %Y",
    "%b %d, %Y",
    "%Y-%m-%d",
    "%d %B %Y",
    "%B %Y",
)

_AVAILABILITY_SCHEMA = pa.schema(
    [
        ("item_id", pa.string()),
        ("avail_ts", pa.int64()),
    ]
)


def _parse_date(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    return None


def _extract_avail_ts(row: Mapping[str, Any]) -> int | None:
    details = row.get("details")
    if not isinstance(details, Mapping):
        return None
    for key in ("Date First Available", "Release date", "Release Date"):
        parsed = _parse_date(details.get(key))
        if parsed is not None:
            return parsed
    return None


def _iter_meta(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield record


def build_item_availability(
    meta_sources: Iterable[tuple[str, str | Path]],
    output_path: str | Path,
    *,
    valid_item_ids: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """Build ``item_availability.parquet`` with ``(item_id, avail_ts)`` from raw metadata.

    Parameters
    ----------
    meta_sources:
        Sequence of ``(domain, meta_path)`` pairs pointing to raw ``.jsonl`` or
        ``.jsonl.gz`` metadata files. Missing files are skipped only when empty;
        pass existing metadata paths for Stage 4 / CLI execution.
    output_path:
        Destination parquet file path.
    valid_item_ids:
        Optional set of namespaced ``item_id`` strings to restrict extraction to
        items present in Stage 3/4 mappings or corpus.
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    avail_by_item: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    total_rows = 0

    for domain, raw_path in meta_sources:
        meta_path = Path(raw_path)
        if not meta_path.exists():
            raise FileNotFoundError(f"Metadata source for domain {domain!r} not found: {meta_path}")
        dom_hits = 0
        for row in _iter_meta(meta_path):
            total_rows += 1
            raw_asin = row.get("parent_asin") or row.get("asin")
            if not isinstance(raw_asin, str) or not raw_asin.strip():
                continue
            raw_asin = raw_asin.strip()
            item_id = raw_asin if "::" in raw_asin else f"{domain}::{raw_asin}"
            if valid_item_ids is not None and item_id not in valid_item_ids:
                continue
            if item_id in avail_by_item:
                continue
            avail_ts = _extract_avail_ts(row)
            if avail_ts is None:
                continue
            avail_by_item[item_id] = avail_ts
            dom_hits += 1
        domain_counts[domain] = dom_hits

    sorted_items = sorted(avail_by_item.items())
    table = pa.table(
        {
            "item_id": pa.array([item_id for item_id, _ in sorted_items], type=pa.string()),
            "avail_ts": pa.array([ts for _, ts in sorted_items], type=pa.int64()),
        },
        schema=_AVAILABILITY_SCHEMA,
    )
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    pq.write_table(table, tmp_path)
    tmp_path.replace(out_path)

    return {
        "output_path": str(out_path),
        "items_with_avail_ts": len(sorted_items),
        "total_meta_rows": total_rows,
        "by_domain": domain_counts,
    }
