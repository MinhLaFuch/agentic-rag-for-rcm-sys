"""Q13 recheck part 1: 'Date First Available' coverage in raw meta `details`.

Streams the three raw meta_*.jsonl.gz files, extracts parent_asin +
details['Date First Available'] (plus counts of other date-like detail keys),
saves investigations/q13b_date_available.parquet, then joins against
corpus items.first_seen_ts (sqlite, read-only) and reports:
  - coverage per domain (% of corpus items with a parseable date)
  - lag = first_seen_ts - date_available (days): how much earlier/later the
    proxy is vs the metadata availability date
  - % items where date_available is AFTER first_seen (proxy says item was
    interacted before it was "available" -> noise) and vice versa.

Read-only. Output: investigations/q13b_date_available.json
"""
from __future__ import annotations

import gzip
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT_PARQUET = Path(__file__).parent / "q13b_date_available.parquet"
OUT_JSON = Path(__file__).parent / "q13b_date_available.json"

META = {
    "Electronics": "resource/raw/meta_Electronics.jsonl.gz",
    "Toys_and_Games": "resource/raw/meta_Toys_and_Games.jsonl.gz",
    "Video_Games": "resource/raw/meta_Video_Games.jsonl.gz",
}
DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"

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


def main() -> None:
    rows = []
    for domain, path in META.items():
        n = 0
        with gzip.open(ROOT / path, "rt", encoding="utf-8") as f:
            for line in f:
                n += 1
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                det = r.get("details") or {}
                # details may be dict or list-of-pairs depending on scrape
                if isinstance(det, dict):
                    dfa = det.get("Date First Available")
                    date_keys = sum(
                        1 for k in det
                        if re.search(r"date|avail|release", str(k), re.I))
                else:
                    dfa = None
                    date_keys = 0
                    for k, v in det:
                        if re.search(r"date|avail|release", str(k), re.I):
                            if dfa is None and "avail" in str(k).lower():
                                dfa = v
                            date_keys += 1
                asin = r.get("parent_asin")
                if asin:
                    rows.append((domain, asin, dfa if isinstance(dfa, str) else None,
                                 int(date_keys)))
        print(f"{domain}: {n:,} meta rows -> {len(rows):,} cumulative", flush=True)

    df = pd.DataFrame(rows, columns=["domain", "asin", "date_available_raw", "n_date_keys"])
    df["date_available_ts"] = df["date_available_raw"].map(parse_date)
    df.to_parquet(OUT_PARQUET, index=False)
    print(f"saved {OUT_PARQUET} ({len(df):,} rows)", flush=True)

    # join to corpus first_seen_ts
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    items = pd.DataFrame(conn.execute(
        "SELECT item_id, domain, first_seen_ts FROM items").fetchall(),
        columns=["item_id", "domain", "first_seen_ts"])
    items["asin"] = items["item_id"].str.split("::").str[-1]
    m = items.merge(df, on=["domain", "asin"], how="left",
                    suffixes=("", "_meta"))

    report = {"method": "stream raw meta_*.jsonl.gz; details['Date First Available'] "
                        "parsed with %B %d %Y etc; joined to items.first_seen_ts on "
                        "(domain, parent_asin); lag_days = (first_seen - date_available)/86400000",
              "n_meta_rows": int(len(df)),
              "coverage": {}, "lag": {}, "examples": []}
    DAY = 86400000.0
    for dom, g in m.groupby("domain"):
        has = g["date_available_ts"].notna()
        both = g[has & g["first_seen_ts"].notna()].copy()
        lag = (both["first_seen_ts"] - both["date_available_ts"]) / DAY
        report["coverage"][dom] = {
            "corpus_items": int(len(g)),
            "with_date_available_raw": int(g["date_available_raw"].notna().sum()),
            "with_parseable_date": int(has.sum()),
            "pct_parseable": round(100 * has.mean(), 2),
        }
        if len(both):
            report["lag"][dom] = {
                "n_both": int(len(both)),
                "lag_days_median": float(lag.median()),
                "lag_days_p10": float(lag.quantile(0.1)),
                "lag_days_p90": float(lag.quantile(0.9)),
                "pct_date_after_first_seen": round(100 * (lag < 0).mean(), 2),
                "pct_lag_gt_365d": round(100 * (lag > 365).mean(), 2),
                "pct_lag_lt_30d": round(100 * (lag < 30).mean(), 2),
            }
        # examples: 3 rows each direction
        ex = both.assign(lag_days=lag).sort_values("lag_days")
        report["examples"].extend(
            [{"domain": r.domain, "item_id": r.item_id,
              "date_available": str(r.date_available_raw),
              "first_seen_ts": int(r.first_seen_ts),
              "lag_days": round(float(r.lag_days), 1)}
             for r in pd.concat([ex.head(2), ex.tail(2)]).itertuples()])
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    print("wrote", OUT_JSON, flush=True)


if __name__ == "__main__":
    main()
