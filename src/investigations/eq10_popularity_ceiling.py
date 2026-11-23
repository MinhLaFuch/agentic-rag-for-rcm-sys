"""E-Q10: pure-popularity recall ceiling (saved version of ad hoc probe).

Rank whole catalog by rating_number DESC (NULLs last, item_id tiebreak —
FilterTool ORDER BY semantics), measure recall of the 196 held-out campaign_005
targets at k=10/100/1000/10000/100000, global + per-domain. Saves
investigations/eq10_popularity_ceiling.json with example rows.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
ITEM2ID = ROOT / "resource/mapped/multi_domain/item2id.json"
REQS = ROOT / "experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/requests.jsonl"
OUT = Path(__file__).parent / "eq10_popularity_ceiling.json"


def main() -> None:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = conn.execute("SELECT item_id, rating_number FROM items").fetchall()
    df = pd.DataFrame(rows, columns=["item_id", "rn"])
    df["rn"] = df["rn"].fillna(-1.0)
    # FilterTool semantics: ORDER BY rating_number IS NULL, rating_number DESC, item_id
    df = df.sort_values(["rn", "item_id"], ascending=[False, True], kind="mergesort")
    df["rank"] = np.arange(len(df))
    rank_map = dict(zip(df.item_id, df["rank"]))

    item2id = json.loads(ITEM2id.read_text(encoding="utf-8")) if False else json.loads(ITEM2ID.read_text(encoding="utf-8"))
    id2item = {v: k for k, v in item2id.items()}
    requests = [json.loads(l) for l in open(REQS, encoding="utf-8")]
    targets = []
    for r in requests:
        for t in r.get("targets", []):
            nm = id2item.get(t)
            if nm:
                targets.append({"request_id": r["request_id"], "kind": r.get("kind"),
                                "item_id": nm, "domain": nm.split("::", 1)[0]})
    for t in targets:
        t["pop_rank"] = int(rank_map.get(t["item_id"], len(df)))

    def recall(sub, ks=(10, 100, 1000, 10000, 100000)):
        n = len(sub)
        return {f"recall@{k}": round(sum(1 for t in sub if t["pop_rank"] < k) / n, 4)
                for k in ks} | {"n": n,
                "median_rank": float(np.median([t["pop_rank"] for t in sub]))}

    report = {
        "method": "ORDER BY rating_number DESC, item_id (NULLs last); "
                  "global catalog rank; targets = 196 campaign_005 exp_5 held-out",
        "ordering_note": "rating_number = raw Amazon rating count (unmasked main.items); "
                         "under eval masking this ordering degenerates to item_id (Q18/Q4)",
        "global": recall(targets),
        "per_domain": {},
        "rank_pctiles": {str(p): float(np.percentile([t["pop_rank"] for t in targets], p))
                         for p in (10, 25, 50, 75, 90)},
        "examples": sorted(targets, key=lambda t: t["pop_rank"])[:5] +
                    sorted(targets, key=lambda t: -t["pop_rank"])[:3],
    }
    for dom in ("Video_Games", "Toys_and_Games", "Electronics"):
        report["per_domain"][dom] = recall([t for t in targets if t["domain"] == dom],
                                           ks=(100, 1000, 10000))
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("global", "per_domain", "rank_pctiles")}, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
