"""Q10 follow-up: category-level hit rate — is exact-item matching too strict?

For each campaign_005 exp_5 request: did the agent's final `recommended` list
contain an item sharing a category with ANY held-out target?

Granularity tiers (a recommendation "hits" a target if they share):
  - domain_match:        same domain prefix (trivial baseline)
  - main_cat_match:      same items.main_category
  - any_cat_overlap:     share >=1 item_categories value (includes mega-cats
                         like 'Electronics' — generous)
  - specific_cat_overlap: share >=1 item_categories value EXCLUDING the
                         top-15 mega categories by member count (fine-grained)

Per request: target_hit = fraction of that request's targets hit by >=1
recommendation; also request-level any-hit. Report overall + by request kind.

Read-only. Output: investigations/q10_category_hit.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
RUN = Path("experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1")
ITEM2ID = Path("resource/mapped/multi_domain/item2id.json")
DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
OUT = Path(__file__).parent / "q10_category_hit.json"
MEGA_N = 15


def main() -> None:
    item2id = json.loads(ITEM2ID.read_text(encoding="utf-8"))
    id2item = {v: k for k, v in item2id.items()}
    requests = {r["request_id"]: r for r in
                (json.loads(l) for l in open(RUN / "requests.jsonl", encoding="utf-8"))}
    trajs = [json.loads(l) for l in open(RUN / "trajectories.jsonl", encoding="utf-8")]
    print(f"requests={len(requests)} trajectories={len(trajs)}", flush=True)

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    # mega categories = top-N by member count
    mega = {r[0] for r in conn.execute(
        "SELECT category FROM item_categories GROUP BY category "
        "ORDER BY COUNT(*) DESC LIMIT ?", (MEGA_N,))}
    print("mega cats excluded:", sorted(mega)[:5], "...", flush=True)

    # collect all item ids needed
    rec_ids, tgt_ids = set(), set()
    for t in trajs:
        rec_ids.update(t.get("recommended") or [])
    for rid, r in requests.items():
        for i in r.get("targets", []):
            nm = id2item.get(i)
            if nm:
                tgt_ids.add(nm)
    all_ids = sorted(rec_ids | tgt_ids)
    print(f"items needed: {len(all_ids):,} (rec={len(rec_ids)}, tgt={len(tgt_ids)})",
          flush=True)

    # categories per item
    cats = defaultdict(set)       # item -> all item_categories
    spec_cats = defaultdict(set)  # item -> non-mega categories
    main_cat = {}
    CHUNK = 5000
    for s in range(0, len(all_ids), CHUNK):
        chunk = all_ids[s:s + CHUNK]
        ph = ",".join("?" for _ in chunk)
        for iid, cat in conn.execute(
                f"SELECT item_id, category FROM item_categories WHERE item_id IN ({ph})",
                chunk).fetchall():
            cats[iid].add(cat)
            if cat not in mega:
                spec_cats[iid].add(cat)
        for iid, mc in conn.execute(
                f"SELECT item_id, main_category FROM main.items WHERE item_id IN ({ph})",
                chunk).fetchall():
            if mc:
                main_cat[iid] = mc
    print("categories loaded", flush=True)

    def domain(iid: str) -> str:
        return iid.split("::")[0] if "::" in iid else ""

    tiers = ["domain_match", "main_cat_match", "any_cat_overlap", "specific_cat_overlap"]
    # accumulate: per request -> per tier -> per target hit?
    results = []
    exact_hits = 0
    n_targets_total = 0
    for t in trajs:
        rid = t["request_id"]
        req = requests.get(rid)
        if req is None:
            continue
        recs = [i for i in (t.get("recommended") or []) if i]
        tgts = [id2item[i] for i in req.get("targets", []) if i in id2item]
        n_targets_total += len(tgts)
        exact = set(tgts) & set(recs)
        exact_hits += len(exact)
        row = {"request_id": rid, "kind": req.get("kind"),
               "segment": req.get("segment"), "n_recommended": len(recs),
               "n_targets": len(tgts), "exact_hits": len(exact)}
        for tier in tiers:
            tgt_hit = 0
            for tg in tgts:
                hit = False
                for rc in recs:
                    if tier == "domain_match":
                        ok = domain(rc) == domain(tg)
                    elif tier == "main_cat_match":
                        ok = main_cat.get(rc) is not None and main_cat.get(rc) == main_cat.get(tg)
                    elif tier == "any_cat_overlap":
                        ok = bool(cats.get(rc, set()) & cats.get(tg, set()))
                    else:
                        ok = bool(spec_cats.get(rc, set()) & spec_cats.get(tg, set()))
                    if ok:
                        hit = True
                        break
                tgt_hit += int(hit)
            row[f"{tier}_target_hits"] = tgt_hit
            row[f"{tier}_target_hit_rate"] = round(tgt_hit / len(tgts), 4) if tgts else None
        results.append(row)

    rdf = __import__("pandas").DataFrame(results)
    summary = {
        "method": "trajectory.recommended vs requests.targets; category tiers "
                  "as defined; mega cats = top-15 item_categories by members",
        "n_requests": len(results), "n_targets": int(n_targets_total),
        "exact_item_hits": int(exact_hits),
        "exact_item_hit_rate": round(exact_hits / max(n_targets_total, 1), 4),
        "overall": {}, "by_kind": {},
    }
    for tier in tiers:
        col = f"{tier}_target_hits"
        summary["overall"][tier] = round(
            float(rdf[col].sum() / max(n_targets_total, 1)), 4)
        summary["overall"][f"{tier}_request_any_hit_rate"] = round(
            float((rdf[col] > 0).mean()), 4)
    for kind, g in rdf.groupby("kind"):
        nt = int(g.n_targets.sum())
        summary["by_kind"][kind] = {
            "n_requests": int(len(g)), "n_targets": nt,
            "exact_hit_rate": round(float(g.exact_hits.sum() / max(nt, 1)), 4),
            **{tier: round(float(g[f"{tier}_target_hits"].sum() / max(nt, 1)), 4)
               for tier in tiers},
        }
    # examples: requests with exact=0 but specific_cat hit>0 (near-misses)
    near = rdf[(rdf.exact_hits == 0) & (rdf.specific_cat_overlap_target_hits > 0)]
    summary["near_miss_examples"] = near.head(8)[
        ["request_id", "kind", "n_targets", "n_recommended",
         "specific_cat_overlap_target_hits", "any_cat_overlap_target_hits",
         "domain_match_target_hits"]].to_dict("records")
    summary["n_near_miss_requests"] = int(len(near))

    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                   encoding="utf-8")
    rdf.to_parquet(Path(__file__).parent / "q10_category_hit_requests.parquet",
                   index=False)
    print(json.dumps(summary["overall"], indent=1))
    print(json.dumps(summary["by_kind"], indent=1))
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
