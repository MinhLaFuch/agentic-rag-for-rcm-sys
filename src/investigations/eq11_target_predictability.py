"""E-Q11: do held-out targets share ANY surface signal with their request?

Fixed target set: campaign_005 exp_5 run_1 requests.jsonl (152 requests, 196 targets).

For each target, three INDEPENDENT signal definitions (plus their union):
  (a) same category as seed_item_id     — target cats ∩ seed cats ≠ ∅
  (b) token overlap with request text   — target title tokens ∩ request tokens ≠ ∅
  (c) same category as any history item — target cats ∩ ∪(history item cats) ≠ ∅
      (history = train.parquet interactions for the request's user_idx,
       global item_idx -> namespaced id -> item_categories; cold users → n/a)

Reported per request kind and overall. Read-only; outputs
investigations/eq11_target_predictability.json
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RUN = Path("experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1")
DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
ITEM2ID = Path("resource/mapped/multi_domain/item2id.json")
OUT = Path(__file__).parent / "eq11_target_predictability.json"

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(text.lower()) if len(t) >= 3}


def cats_for(conn: sqlite3.Connection, item_ids: list[str]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for i in range(0, len(item_ids), 400):
        chunk = item_ids[i:i + 400]
        marks = ",".join("?" * len(chunk))
        for iid, cat in conn.execute(
                f"SELECT item_id, category FROM item_categories WHERE item_id IN ({marks})", chunk):
            out[iid].add(cat)
    return out


def titles_for(conn: sqlite3.Connection, item_ids: list[str]) -> dict[str, str]:
    out = {}
    for i in range(0, len(item_ids), 400):
        chunk = item_ids[i:i + 400]
        marks = ",".join("?" * len(chunk))
        for iid, title in conn.execute(
                f"SELECT item_id, title FROM items WHERE item_id IN ({marks})", chunk):
            out[iid] = title or ""
    return out


def main() -> None:
    requests = [json.loads(l) for l in open(RUN / "requests.jsonl", encoding="utf-8")]
    item2id = json.loads(ITEM2ID.read_text(encoding="utf-8"))
    id2item = {v: k for k, v in item2id.items()}

    # gather all needed item ids: targets, seeds, and (later) history items
    req_targets = []
    all_item_ids = set()
    for r in requests:
        tnames = [id2item[i] for i in r.get("targets", []) if i in id2item]
        req_targets.append((r, tnames))
        all_item_ids.update(tnames)
        if r.get("seed_item_id"):
            all_item_ids.add(r["seed_item_id"])

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA query_only=ON")

    # categories + titles for targets/seeds first
    cat_map = cats_for(conn, sorted(all_item_ids))
    title_map = titles_for(conn, sorted(all_item_ids))

    # history items per request user (train.parquet, global idx -> namespaced id)
    need_users = {r["user_idx"] for r, _ in req_targets}
    hist_items: dict[int, list[str]] = defaultdict(list)
    train = pd.read_parquet("resource/splits/multi_domain/train.parquet",
                            columns=["user_idx", "item_idx"])
    sub = train[train.user_idx.isin(need_users)]
    for uidx, grp in sub.groupby("user_idx"):
        hist_items[int(uidx)] = [id2item[i] for i in grp.item_idx.to_numpy() if i in id2item]
    # categories for all history items (batch)
    all_hist_ids = sorted({iid for ids in hist_items.values() for iid in ids})
    hist_cat_map = cats_for(conn, all_hist_ids)

    per_target = []
    for r, tnames in req_targets:
        req_toks = tokens(r.get("text", ""))
        seed_cats = cat_map.get(r.get("seed_item_id"), set()) if r.get("seed_item_id") else set()
        user_hist_cats: set[str] = set()
        for hid in hist_items.get(r["user_idx"], []):
            user_hist_cats |= hist_cat_map.get(hid, set())
        kind = r.get("kind", "?")
        for t in tnames:
            tc = cat_map.get(t, set())
            tt = tokens(title_map.get(t, ""))
            sig_a = bool(tc & seed_cats) if seed_cats else None   # None = no seed
            sig_b = bool(tt & req_toks) if req_toks else False
            sig_c = bool(tc & user_hist_cats) if user_hist_cats else (None if not hist_items.get(r["user_idx"]) else False)
            union = any(s is True for s in (sig_a, sig_b, sig_c))
            per_target.append({
                "request_id": r["request_id"], "kind": kind, "target": t,
                "seed": r.get("seed_item_id"),
                "n_target_cats": len(tc), "n_seed_cats": len(seed_cats),
                "n_hist_items": len(hist_items.get(r["user_idx"], [])),
                "n_hist_cats": len(user_hist_cats),
                "signal_seed_cat": sig_a, "signal_text_overlap": sig_b,
                "signal_history_cat": sig_c, "signal_union": union,
                "target_title": title_map.get(t, "")[:80],
                "target_cats": sorted(tc)[:5],
            })

    # aggregate
    def agg(rows):
        n = len(rows)
        def frac(key):
            vals = [r[key] for r in rows if r[key] is not None]
            return {"n_defined": len(vals), "n_true": sum(1 for v in vals if v),
                    "frac": (sum(1 for v in vals if v) / len(vals)) if vals else None}
        return {
            "n_targets": n,
            "seed_cat": frac("signal_seed_cat"),
            "text_overlap": frac("signal_text_overlap"),
            "history_cat": frac("signal_history_cat"),
            "union": {"n_true": sum(1 for r in rows if r["signal_union"]),
                      "frac": sum(1 for r in rows if r["signal_union"]) / n if n else None},
            "no_signal_union": sum(1 for r in rows if not r["signal_union"]),
        }

    by_kind = defaultdict(list)
    for r in per_target:
        by_kind[r["kind"]].append(r)

    report = {
        "n_requests": len(requests), "n_targets": len(per_target),
        "overall": agg(per_target),
        "by_kind": {k: agg(v) for k, v in sorted(by_kind.items())},
        "examples_no_signal": [r for r in per_target if not r["signal_union"]][:8],
        "examples_signal": [r for r in per_target if r["signal_union"]][:5],
        "per_target": per_target,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("n_requests", "n_targets", "overall", "by_kind")},
                     ensure_ascii=False, indent=2)[:4000])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
