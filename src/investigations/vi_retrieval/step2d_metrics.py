"""Step 2d: aggregate arms (a)-(e) metrics -> step2_metrics.json.

Arms:
  (a) bm25 raw VI query            -> bm25_ranks universe=restricted|full, arm=vi
  (b) minilm dense raw VI          -> dense_ranks minilm/{restricted,full}/vi
  (c) LLM-translated -> BM25       -> bm25 arm=en (en_query = faithful translation)
  (d) translated -> minilm dense   -> dense minilm/*/en
  (e) multilingual dense raw VI    -> dense bge-m3|e5base restricted/vi

(f) hybrid RRF is computed separately in step2e_hybrid.py (needs top-k lists).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
TOPK = 1500
KS = (10, 50, 200, 1000)


def metrics(ranks: pd.Series) -> dict:
    s = ranks.dropna().astype(float)
    n = len(ranks)
    out = {"n": int(n)}
    for k in KS:
        out[f"recall@{k}"] = float((s <= k).sum() / n)
    out["mrr"] = float((1.0 / s[s <= TOPK]).sum() / n) if len(s) else 0.0
    return out


def main() -> None:
    bm = pd.read_parquet(OUT / "bm25_ranks.parquet")
    dn = pd.read_parquet(OUT / "dense_ranks.parquet")
    res = {}

    def add(name, df, rank_col="rank"):
        res[name] = metrics(df[rank_col])

    # (a) BM25 raw VI — restricted + full
    add("a_bm25_vi_restricted", bm[(bm.universe == "restricted") & (bm.arm == "vi")])
    add("a_bm25_vi_full", bm[(bm.universe == "full") & (bm.arm == "vi")])
    # (c) translated -> BM25
    add("c_bm25_en_restricted", bm[(bm.universe == "restricted") & (bm.arm == "en")])
    add("c_bm25_en_full", bm[(bm.universe == "full") & (bm.arm == "en")])

    # (b)+(d) minilm dense
    for uni in ("restricted", "full"):
        add(f"b_minilm_dense_vi_{uni}", dn[(dn.model == "minilm") & (dn.universe == uni) & (dn.arm == "vi")])
        add(f"d_minilm_dense_en_{uni}", dn[(dn.model == "minilm") & (dn.universe == uni) & (dn.arm == "en")])
    # (e) multilingual dense raw VI (restricted only)
    for m in ("bge-m3", "e5base"):
        add(f"e_{m}_vi_restricted", dn[(dn.model == m) & (dn.universe == "restricted") & (dn.arm == "vi")])
        add(f"e_{m}_en_restricted", dn[(dn.model == m) & (dn.universe == "restricted") & (dn.arm == "en")])

    (OUT / "step2_metrics.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
