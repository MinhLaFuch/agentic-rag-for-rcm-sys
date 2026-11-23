"""Step 3: language-fair target predictability (redo of E-Q11 text signal).

For each of the 196 targets:
  - translate the request text to English (faithful, from step2b output)
  - token overlap: target title tokens ∩ translated-request tokens (vs old VI)
  - BM25 rank of target among its category peers using translated request
    (restricted to items sharing >=1 target category, production FTS path)
  - multilingual-dense rank among category peers (best arm from step2, raw VI)

Compare new "share nothing" fraction + revised ceiling vs old 11.7% / 24.5% / 62%.

Outputs: investigations/vi_retrieval/step3_predictability.json + .parquet
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DB = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
sys.path.insert(0, str(ROOT))
from package.tools.retrieval._helper import _tokenize  # noqa: E402

TOKEN_RE = re.compile(r"[a-z0-9]+")
TOP_FETCH = 1500


def tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(text.lower()) if len(t) >= 3}


def main() -> None:
    eq11 = json.loads((ROOT / "investigations/eq11_target_predictability.json").read_text(encoding="utf-8"))
    per_target = eq11["per_target"]

    # request texts (VI) + faithful EN translations
    reqs = {}
    req_path = (ROOT / "experiments/agent_eval/campaigns/campaign_005/"
                "exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/requests.jsonl")
    with open(req_path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            reqs[r["request_id"]] = r["text"]
    en_trans = {}
    tp = OUT / "request_translations.jsonl"
    if tp.exists():
        for l in tp.read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                en_trans[d["request_id"]] = d.get("en") or d.get("en_text") or ""

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    # category peers per target: items sharing >=1 target category
    all_cats = sorted({c for t in per_target for c in t["target_cats"]})
    cat_items: dict[str, set[str]] = defaultdict(set)
    for i in range(0, len(all_cats), 200):
        chunk = all_cats[i:i + 200]
        marks = ",".join("?" * len(chunk))
        for iid, cat in conn.execute(
                f"SELECT item_id, category FROM item_categories WHERE category IN ({marks})", chunk):
            cat_items[cat].add(iid)

    rows = []
    for t in per_target:
        rid = t["request_id"]
        target = t["target"]
        vi_text = reqs.get(rid, "")
        en_text = en_trans.get(rid, "")

        # token overlap: VI request vs EN translation
        tgt_tokens = tokens(t.get("target_title", ""))
        vi_overlap = bool(tgt_tokens & tokens(vi_text))
        en_overlap = bool(tgt_tokens & tokens(en_text)) if en_text else None

        # BM25 rank among category peers with translated request
        peer_ids = set()
        for c in t["target_cats"]:
            peer_ids |= cat_items.get(c, set())
        peer_ids.discard(target)
        bm25_rank = np.nan
        if en_text and peer_ids:
            toks = _tokenize(en_text)
            if toks:
                match = " OR ".join(f'"{x}"' for x in toks)
                # exact rank among ALL peers, censored at TOP_FETCH: fetch the
                # best TOP_FETCH bm25 hits for the query; a peer ranked above
                # the target necessarily appears before it in this list.
                hits = []
                for iid, rn in conn.execute(
                        f"SELECT items.item_id, items.rating_number "
                        f"FROM items_fts JOIN items ON items.rowid=items_fts.rowid "
                        f"WHERE items_fts MATCH ? ORDER BY bm25(items_fts) LIMIT ?",
                        [match, TOP_FETCH]):
                    hits.append(iid)
                if target in hits:
                    pos = hits.index(target) + 1
                    above = hits[:pos - 1]
                    bm25_rank = float(1 + sum(1 for iid in above if iid in peer_ids))
                else:
                    bm25_rank = np.nan  # target not in top TOP_FETCH -> censored

        rows.append({
            "request_id": rid, "kind": t["kind"], "target": target,
            "target_cats": t["target_cats"], "n_peers": len(peer_ids),
            "vi_overlap": vi_overlap, "en_overlap": en_overlap,
            "en_text": en_text, "bm25_peer_rank": bm25_rank,
            "old_text_overlap": t["signal_text_overlap"],
        })
    conn.close()

    df = pd.DataFrame(rows)
    df.to_parquet(OUT / "step3_predictability.parquet", index=False)

    def frac(mask, col):
        sub = df[mask]
        return {"n": len(sub), "frac": float(sub[col].mean()) if len(sub) else None}

    summary = {
        "n_targets": len(df),
        "old_text_overlap_frac": float(df["old_text_overlap"].mean()),
        "vi_token_overlap_frac": float(df["vi_overlap"].mean()),
        "en_token_overlap_frac": float(df["en_overlap"].dropna().mean()) if df["en_overlap"].notna().any() else None,
        "bm25_peer_rank": {
            "n": int(df["bm25_peer_rank"].notna().sum()),
            "recall@10": float((df["bm25_peer_rank"] <= 10).mean()),
            "recall@50": float((df["bm25_peer_rank"] <= 50).mean()),
            "recall@200": float((df["bm25_peer_rank"] <= 200).mean()),
            "median_rank": float(df["bm25_peer_rank"].median()),
        },
        "by_kind": {},
    }
    for kind, g in df.groupby("kind"):
        summary["by_kind"][kind] = {
            "n": len(g),
            "old_overlap": float(g["old_text_overlap"].mean()),
            "vi_overlap": float(g["vi_overlap"].mean()),
            "en_overlap": float(g["en_overlap"].mean()) if g["en_overlap"].notna().any() else None,
            "bm25@200": float((g["bm25_peer_rank"] <= 200).mean()),
        }
    (OUT / "step3_predictability.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
