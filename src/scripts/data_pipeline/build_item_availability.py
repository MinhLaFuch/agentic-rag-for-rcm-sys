"""Build item_availability.parquet — per-item 'Date First Available' timestamps.

Scans resource/raw/meta_<Domain>.jsonl.gz, extracts
``details["Date First Available"]``, parses it to epoch-ms, and writes a
parquet with columns ``item_id`` (``Domain::parent_asin``) and ``avail_ts``.
Only parseable dates are kept; junk-date filtering (e.g. "July 6, 1931")
happens later inside ``apply_metadata_policy`` where ``first_seen_ts`` is
available for cross-validation.

Usage:
    python scripts/data_pipeline/build_item_availability.py \
        --raw-dir resource/raw --out resource/corpus/multi_domain/item_availability.parquet
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DATE_FORMATS = ["%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y", "%Y", "%m/%d/%Y", "%Y-%m-%d"]


def parse_date(s) -> float | None:
    if not isinstance(s, str):
        return None
    s = s.strip()
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).replace(tzinfo=timezone.utc).timestamp() * 1000.0
        except ValueError:
            continue
    return None


def iter_meta(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def extract_avail_ts(row: dict) -> float | None:
    det = row.get("details") or {}
    dfa = None
    if isinstance(det, dict):
        dfa = det.get("Date First Available")
    else:
        for k, v in det:
            if "avail" in str(k).lower():
                dfa = v
                break
    return parse_date(dfa)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", type=Path, default=Path("resource/raw"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--domains", nargs="*", default=None,
                    help="domain names (file stems minus meta_); default = all meta_*.jsonl.gz")
    args = ap.parse_args()

    if args.domains:
        files = [args.raw_dir / f"meta_{d}.jsonl.gz" for d in args.domains]
    else:
        files = sorted(args.raw_dir.glob("meta_*.jsonl.gz"))

    rows = []
    for path in files:
        if not path.exists():
            print(f"skip missing {path}", flush=True)
            continue
        domain = path.name[len("meta_"):-len(".jsonl.gz")]
        n = kept = 0
        seen = set()
        for r in iter_meta(path):
            n += 1
            asin = r.get("parent_asin")
            if not asin or asin in seen:
                continue
            ts = extract_avail_ts(r)
            if ts is None:
                continue
            seen.add(asin)
            rows.append((f"{domain}::{asin}", ts))
            kept += 1
        print(f"{domain}: {n:,} rows -> {kept:,} availability dates", flush=True)

    df = pd.DataFrame(rows, columns=["item_id", "avail_ts"])
    df = df.drop_duplicates("item_id", keep="first")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"saved {len(df):,} items -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
