"""Patch q11_q13_q16_probes.json: fix Q16 Spearman (idx bug) + Q11 user2id keys."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
P = Path(__file__).parent / "q11_q13_q16_probes.json"
SPLITS = ROOT / "resource/splits/multi_domain"


def main() -> None:
    d = json.loads(P.read_text(encoding="utf-8"))
    item2id = json.loads((ROOT / "resource/mapped/multi_domain/item2id.json").read_text(encoding="utf-8"))
    id2item = {v: k for k, v in item2id.items()}

    conn = sqlite3.connect("file:resource/corpus/multi_domain/corpus_multi_domain.sqlite?mode=ro", uri=True)
    rn_by_name = {iid: (float(r) if r is not None else np.nan)
                  for iid, r in conn.execute("SELECT item_id, rating_number FROM items")}
    # item_idx -> rating_number
    rn_by_idx = np.full(len(item2id), np.nan)
    for idx, nm in id2item.items():
        rn_by_idx[idx] = rn_by_name.get(nm, np.nan)

    train = pd.read_parquet(SPLITS / "train.parquet", columns=["item_idx"])
    val = pd.read_parquet(SPLITS / "validation.parquet", columns=["item_idx"])
    test = pd.read_parquet(SPLITS / "test.parquet", columns=["item_idx"])
    item_counts = train["item_idx"].value_counts()
    held_counts = pd.concat([val["item_idx"], test["item_idx"]]).value_counts()

    def spear(counts):
        common = counts.index.intersection(pd.Index(np.nonzero(~np.isnan(rn_by_idx))[0]))
        x = rn_by_idx[common.to_numpy()]
        y = counts.loc[common].to_numpy(dtype=float)
        m = ~np.isnan(x)
        return float(pd.Series(x[m]).corr(pd.Series(y[m]), method="spearman")), int(m.sum())

    st, nt = spear(item_counts)
    sh, nh = spear(held_counts)
    d["Q16_rating_number"]["spearman_vs_train_interaction_count"] = st
    d["Q16_rating_number"]["spearman_vs_heldout_interaction_count"] = sh
    d["Q16_rating_number"]["n_common_train"] = nt
    d["Q16_rating_number"]["n_common_heldout"] = nh

    # Q11 user2id sample keys (correct path)
    u2 = json.loads((ROOT / "resource/mapped/multi_domain/user2id.json").read_text(encoding="utf-8"))
    keys = list(u2.keys())
    d["Q11_cross_domain"]["user2id_sample_keys"] = keys[:3]
    d["Q11_cross_domain"]["user2id_n"] = len(keys)
    d["Q11_cross_domain"]["user2id_has_domain_prefix"] = any("::" in k for k in keys[:50000])

    P.write_text(json.dumps(d, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("spearman train:", st, "heldout:", sh, "n:", nt, nh)
    print("user2id keys:", keys[:2], "has_prefix:", d["Q11_cross_domain"]["user2id_has_domain_prefix"])
    print("patched", P)


if __name__ == "__main__":
    main()
