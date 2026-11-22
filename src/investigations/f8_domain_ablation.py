"""F8 / Q11 follow-up: cross-domain history ablation — OFFLINE exposure analysis.

For each campaign_005 request, replay MemoryTool's profile logic on the user's
fit (train) history under two variants:
  A) full merged history (current behavior)
  B) history restricted to the request's domain

Measures, per request:
  - history loss (n_interactions A vs B)
  - top_categories churn (Jaccard) and whether the TARGET's categories are covered
  - recent_items cross-domain share under A (SimilarTool seed pollution)

Read-only; outputs investigations/f8_domain_ablation.json
"""
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/requests.jsonl"
TRAIN = ROOT / "resource/splits/multi_domain/train.parquet"
CORPUS = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
OUT = Path(__file__).parent / "f8_domain_ablation.json"

TOP_N_CATS = 5      # memory.yaml default
RECENT_N = 10       # memory.yaml default
AS_OF = 1617737606549


def main():
    reqs = []
    for line in REQ.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        reqs.append(r)
    eval_users = sorted({int(r["user_idx"]) for r in reqs if r.get("user_idx") not in (None, "None")})
    print(f"requests={len(reqs)} eval_users={len(eval_users)}")

    # fit history for eval users only
    train = pd.read_parquet(TRAIN, filters=[("user_idx", "in", eval_users)])
    train = train[train["timestamp"] <= AS_OF]
    print(f"fit rows for eval users: {len(train):,}")

    # request domain: seed_item_id prefix, else first target's item domain
    item2id = json.loads((ROOT / "resource/mapped/multi_domain/item2id.json").read_text(encoding="utf-8"))
    id2item = {v: k for k, v in item2id.items()}
    item_domain = {}
    for name, idx in item2id.items():
        item_domain[idx] = name.split("::", 1)[0]

    def req_domain(r):
        sid = r.get("seed_item_id")
        if sid and "::" in sid:
            return sid.split("::", 1)[0]
        tg = r.get("targets")
        if isinstance(tg, str):
            tg = json.loads(tg)
        if tg:
            d = item_domain.get(int(tg[0]))
            if d:
                return d
        return None

    # categories per item for involved items (history + targets)
    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    involved = set(train["item_idx"].unique().tolist())
    for r in reqs:
        tg = r.get("targets")
        if isinstance(tg, str):
            tg = json.loads(tg)
        involved.update(int(t) for t in (tg or []))
    involved_names = [id2item[i] for i in involved if i in id2item]
    item_cats = defaultdict(set)
    CH = 20000
    for i in range(0, len(involved_names), CH):
        chunk = involved_names[i:i + CH]
        ph = ",".join("?" for _ in chunk)
        for iid, cat in conn.execute(
            f"SELECT item_id, category FROM item_categories WHERE item_id IN ({ph})", chunk
        ):
            # map back via item2id
            item_cats[item2id[iid]].add(cat)
    print(f"items with categories: {len(item_cats):,}")

    # per-user history grouped
    hist_by_user = {u: g for u, g in train.groupby("user_idx")}

    def profile(hist, domain=None):
        """Approximate MemoryTool output: top_categories, recent_items, n."""
        h = hist if domain is None else hist[hist["domain"] == domain]
        if h.empty:
            return {"n": 0, "top_categories": [], "recent": []}
        # top_categories: categories of UNIQUE history items, ranked by item count
        uniq_items = h["item_idx"].unique()
        cat_counter = Counter()
        for it in uniq_items:
            for c in item_cats.get(int(it), ()):
                cat_counter[c] += 1
        top_cats = [c for c, _ in cat_counter.most_common(TOP_N_CATS)]
        recent = h.sort_values("timestamp", ascending=False)["item_idx"].head(RECENT_N).tolist()
        return {"n": len(h), "top_categories": top_cats, "recent": [int(x) for x in recent]}

    results = []
    for r in reqs:
        uidx = int(r["user_idx"]) if r.get("user_idx") not in (None, "None") else None
        if uidx is None or uidx not in hist_by_user:
            continue
        d = req_domain(r)
        hist = hist_by_user[uidx]
        pa = profile(hist)
        pb = profile(hist, d) if d else pa
        # target categories (first target)
        tg = r.get("targets")
        if isinstance(tg, str):
            tg = json.loads(tg)
        tgt_cats = set()
        if tg:
            for t in tg[:1]:
                tgt_cats |= item_cats.get(int(t), set())
        recent_domains = [item_domain.get(x) for x in pa["recent"]]
        cross = sum(1 for x in recent_domains if x and d and x != d)
        ja = len(set(pa["top_categories"]) & set(pb["top_categories"])) / max(
            1, len(set(pa["top_categories"]) | set(pb["top_categories"])))
        results.append({
            "request_id": r["request_id"], "kind": r["kind"],
            "request_domain": d,
            "n_hist_A": pa["n"], "n_hist_B": pb["n"],
            "hist_loss_frac": round(1 - pb["n"] / max(1, pa["n"]), 4),
            "topcats_jaccard": round(ja, 3),
            "topcats_A": pa["top_categories"], "topcats_B": pb["top_categories"],
            "target_cats": sorted(tgt_cats),
            "target_cat_in_A": bool(tgt_cats & set(pa["top_categories"])),
            "target_cat_in_B": bool(tgt_cats & set(pb["top_categories"])),
            "recent_cross_domain": cross, "recent_n": len(pa["recent"]),
        })

    # aggregate
    n = len(results)
    def frac(pred):
        return round(sum(1 for x in results if pred(x)) / max(1, n), 4)
    summary = {
        "n_requests": n,
        "mean_hist_loss_frac": round(sum(x["hist_loss_frac"] for x in results) / max(1, n), 4),
        "mean_topcats_jaccard": round(sum(x["topcats_jaccard"] for x in results) / max(1, n), 4),
        "requests_target_cat_in_topcats_A": frac(lambda x: x["target_cat_in_A"]),
        "requests_target_cat_in_topcats_B": frac(lambda x: x["target_cat_in_B"]),
        "B_improves_target_cat": frac(lambda x: x["target_cat_in_B"] and not x["target_cat_in_A"]),
        "B_worsens_target_cat": frac(lambda x: x["target_cat_in_A"] and not x["target_cat_in_B"]),
        "mean_recent_cross_domain_share": round(
            sum(x["recent_cross_domain"] / max(1, x["recent_n"]) for x in results) / max(1, n), 4),
        "requests_with_any_cross_domain_recent": frac(lambda x: x["recent_cross_domain"] > 0),
        "requests_hist_loss_gt_50pct": frac(lambda x: x["hist_loss_frac"] > 0.5),
    }
    OUT.write_text(json.dumps({"summary": summary, "per_request": results}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
