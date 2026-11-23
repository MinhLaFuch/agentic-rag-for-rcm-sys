"""E-Q9: temporal density around the split cutoffs (read-only).

Interactions per calendar month per domain across train+validation+test.
Checks whether the val/test windows sit in atypical periods (seasonality,
COVID bump, scrape artifacts) that would make held-out targets systematically
easier/harder than deployment.

For each cutoff (cutoff_1=1617737606134 train/val, cutoff_2=1651701127817
val/test): report monthly counts for 6 months before/after, vs the trailing
12-month median, per domain and pooled.

Output: investigations/eq9_temporal_density.json (+ .csv of monthly counts)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SPLITS = Path("resource/splits/multi_domain")
CUTOFF_1 = 1617737606134
CUTOFF_2 = 1651701127817
OUT_JSON = Path(__file__).parent / "eq9_temporal_density.json"
OUT_CSV = Path(__file__).parent / "eq9_monthly_counts.csv"


def main() -> None:
    frames = []
    for name in ("train", "validation", "test"):
        df = pd.read_parquet(SPLITS / f"{name}.parquet",
                             columns=["timestamp", "domain"])
        df["split"] = name
        frames.append(df)
    all_df = pd.concat(frames, ignore_index=True)
    print(f"rows: {len(all_df):,}", flush=True)

    all_df["month"] = pd.to_datetime(all_df.timestamp, unit="ms", utc=True) \
        .dt.to_period("M")
    monthly = all_df.groupby(["month", "domain"]).size().unstack(fill_value=0)
    monthly_total = all_df.groupby("month").size()
    monthly.to_csv(OUT_CSV)
    print(monthly_total.describe(), flush=True)

    def window_stats(cutoff_ms: int, label: str) -> dict:
        cmonth = pd.Timestamp(cutoff_ms, unit="ms", tz="UTC").to_period("M")
        idx = monthly_total.index
        pos = idx.get_loc(cmonth)
        before = monthly_total.iloc[max(0, pos - 6):pos]
        after = monthly_total.iloc[pos + 1:pos + 7]
        trailing = monthly_total.iloc[max(0, pos - 12):pos]
        base = float(trailing.median()) if len(trailing) else np.nan
        return {
            "cutoff": label, "cutoff_month": str(cmonth),
            "monthly_counts_before": {str(m): int(v) for m, v in before.items()},
            "monthly_counts_after": {str(m): int(v) for m, v in after.items()},
            "trailing_12m_median": base,
            "after_over_baseline": {
                str(m): round(v / base, 3) for m, v in after.items()} if base else {},
        }

    report = {
        "method": "train+validation+test parquets, group by calendar month x "
                  "domain; window = 6mo before/after each cutoff vs trailing-12m "
                  "median",
        "n_rows": int(len(all_df)),
        "first_month": str(monthly.index.min()), "last_month": str(monthly.index.max()),
        "total_interactions": int(len(all_df)),
        "cutoffs": {
            "cutoff_1_train_val": window_stats(CUTOFF_1, "cutoff_1"),
            "cutoff_2_val_test": window_stats(CUTOFF_2, "cutoff_2"),
        },
        "per_domain_monthly_tail": {
            dom: {str(m): int(v) for m, v in monthly[dom].tail(14).items()}
            for dom in monthly.columns},
        "examples": [],
    }
    # examples: peak/trough months
    top = monthly_total.nlargest(3)
    bot = monthly_total.nsmallest(3)
    report["examples"] = [
        {"month": str(m), "count": int(v), "kind": "peak"} for m, v in top.items()] + \
        [{"month": str(m), "count": int(v), "kind": "trough"} for m, v in bot.items()]

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                   default=str), encoding="utf-8")
    print("wrote", OUT_JSON, flush=True)
    print(json.dumps(report["cutoffs"], indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
