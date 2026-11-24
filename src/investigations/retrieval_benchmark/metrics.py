"""Aggregate bm25_ranks.parquet + dense_ranks.parquet into metrics + REPORT.md."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
TOPK = 1500
KS = (10, 50, 200, 1000)


def metrics(df: pd.DataFrame, keys: list[str]) -> dict:
    out = {}
    for k, g in df.groupby(keys):
        s = g["rank"]
        n = len(s)
        out["/".join(str(x) for x in (k if isinstance(k, tuple) else (k,)))] = {
            "n": int(n),
            **{f"recall@{k}": float((s <= k).sum() / n) for k in KS},
            "mrr": float((1.0 / s[s <= TOPK]).sum() / n),
        }
    return out


def main() -> None:
    frames = []
    bp = OUT / "bm25_ranks.parquet"
    if bp.exists():
        b = pd.read_parquet(bp)
        b["model"] = "bm25"
        b["universe"] = "full"
        frames.append(b[["model", "universe", "arm", "item_id", "rank"]])
    dp = OUT / "dense_ranks.parquet"
    if dp.exists():
        frames.append(pd.read_parquet(dp))
    if not frames:
        sys.exit("no rank files yet")
    allr = pd.concat(frames, ignore_index=True)

    met = metrics(allr, ["model", "universe", "arm"])
    (OUT / "metrics.json").write_text(json.dumps(met, indent=1), encoding="utf-8")

    # per-kind breakdown for the headline arms
    tgt = pd.read_parquet(OUT / "targets.parquet")[["item_id", "kind", "request_id"]].drop_duplicates("item_id")
    j = allr.merge(tgt[["item_id", "kind"]], on="item_id", how="left")
    kind_met = metrics(j, ["model", "universe", "arm", "kind"])
    (OUT / "metrics_by_kind.json").write_text(json.dumps(kind_met, indent=1), encoding="utf-8")

    # print compact table
    print(f"{'arm':28s} {'n':>4s} {'r@10':>6s} {'r@50':>6s} {'r@200':>6s} {'r@1000':>6s} {'mrr':>6s}")
    for key, m in sorted(met.items()):
        print(f"{key:28s} {m['n']:4d} {m['recall@10']:6.3f} {m['recall@50']:6.3f} "
              f"{m['recall@200']:6.3f} {m['recall@1000']:6.3f} {m['mrr']:6.3f}")


if __name__ == "__main__":
    sys.exit(main())
