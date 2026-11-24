"""Probe: would `details["Date First Available"]` fix the first_seen visibility ceiling?

Joins q13b per-item availability dates to corpus items.first_seen_ts, applies a
junk-date cleaning rule, and measures how many of the 36 hidden eval targets
(plus the catalog at large) become visible under an availability-based policy.

Cleaning rule (junk dates observed: "July 6, 1931", "January 1, 1970",
"December 30, 1899", and ~6-9.7% dates AFTER first review):
  accept date_available_ts iff 1995-01-01 <= ts <= first_seen_ts
  (Amazon reviews data starts ~1996; a date after first interaction is impossible)

Effective visibility ts = min(valid_date_available, first_seen_ts).
Items without a valid date keep first_seen_ts (proxy unchanged).

Read-only. Output: investigations/date_available_probe.json
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
CORPUS = HERE.parent / "resource" / "corpus" / "multi_domain" / "corpus_multi_domain.sqlite"
AS_OF = 1617737606549  # campaign_005 eval cutoff (same as q13c)
EARLIEST = datetime(1995, 1, 1, tzinfo=timezone.utc).timestamp() * 1000.0
OUT = HERE / "date_available_probe.json"


def main() -> None:
    dates = pd.read_parquet(HERE / "q13b_date_available.parquet")
    dates["item_id"] = dates["domain"] + "::" + dates["asin"]

    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    items = pd.read_sql_query("SELECT item_id, first_seen_ts FROM items", conn)
    conn.close()

    df = items.merge(dates[["item_id", "date_available_ts"]], on="item_id", how="left")
    df["has_fs"] = df["first_seen_ts"].notna()

    valid = (
        df["date_available_ts"].notna()
        & df["has_fs"]
        & (df["date_available_ts"] >= EARLIEST)
        & (df["date_available_ts"] <= df["first_seen_ts"])
    )
    df["avail_ts"] = df["date_available_ts"].where(valid)
    df["eff_ts"] = df[["avail_ts", "first_seen_ts"]].min(axis=1)

    n = len(df)
    report = {
        "method": "accept date iff 1995-01-01 <= date_available <= first_seen_ts; "
                  "eff_ts = min(avail, first_seen); targets from q13c_targets.parquet",
        "as_of": AS_OF,
        "catalog": {
            "n_items": int(n),
            "n_parseable_raw": int(df["date_available_ts"].notna().sum()),
            "n_valid_after_cleaning": int(valid.sum()),
            "pct_valid": round(100 * valid.mean(), 2),
            "n_eff_earlier_than_first_seen": int((df["avail_ts"].notna() & (df["avail_ts"] < df["first_seen_ts"])).sum()),
        },
    }

    # Targets: hidden under current policy vs under availability policy
    targets = pd.read_parquet(HERE / "q13c_targets.parquet")
    t = targets.merge(df[["item_id", "first_seen_ts", "avail_ts", "eff_ts"]],
                      on="item_id", how="left", suffixes=("", "_c"))
    t["hidden_current"] = t["first_seen_ts"].isna() | (t["first_seen_ts"] > AS_OF)
    t["hidden_avail"] = t["eff_ts"].isna() | (t["eff_ts"] > AS_OF)
    t["recovered"] = t["hidden_current"] & ~t["hidden_avail"]

    report["targets"] = {
        "n": int(len(t)),
        "hidden_current": int(t["hidden_current"].sum()),
        "hidden_avail": int(t["hidden_avail"].sum()),
        "recovered": int(t["recovered"].sum()),
        "recovered_item_ids": t.loc[t["recovered"], "item_id"].tolist(),
        "still_hidden_item_ids": t.loc[t["hidden_avail"], "item_id"].tolist(),
        "by_domain_recovered": t[t["recovered"]].groupby("domain").size().to_dict(),
    }

    # How much earlier does the catalog become visible? (shift distribution)
    shift = (df["first_seen_ts"] - df["avail_ts"]).dropna() / 86400000.0
    report["visibility_shift_days"] = {
        "n": int(len(shift)),
        "median": round(float(shift.median()), 1),
        "p10": round(float(shift.quantile(0.10)), 1),
        "p90": round(float(shift.quantile(0.90)), 1),
    }

    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
