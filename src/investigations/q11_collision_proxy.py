"""Q11 follow-up: can we get *evidence* about cross-domain user-ID collision /
merged-history harm, without external identity data?

Amazon reviewer IDs are account-level, so same-ID = same account is plausible;
the real measurable risk is not ID collision but DOMAIN POLLUTION: a user's
merged cross-domain history feeding domain-inappropriate candidates into
MemoryTool.top_categories / SimilarTool seeds for a request in another domain.

Measurements on the fixed campaign_005 exp_5 request set:
  1. eval users' train-history domain distribution vs request domain
     (request domain = seed_item_id prefix, else majority target domain)
  2. % of history items OUTSIDE the request domain (pollution share)
  3. for multi-domain-history users: is the target domain the majority-history
     domain or a minority one? (if targets come from minority domains, merged
     history may be hurting)
  4. rating-consistency sanity: per-user mean rating per domain — wildly
     different scales could indicate different people (weak signal, reported
     descriptively only)

Read-only. Output: investigations/q11_collision_proxy.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REQS = Path("experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/requests.jsonl")
SPLITS = Path("resource/splits/multi_domain")
ITEM2ID = Path("resource/mapped/multi_domain/item2id.json")
OUT = Path(__file__).parent / "q11_collision_proxy.json"


def main() -> None:
    item2id = json.loads(ITEM2ID.read_text(encoding="utf-8"))
    id2item = {v: k for k, v in item2id.items()}
    requests = [json.loads(l) for l in open(REQS, encoding="utf-8")]

    # request domain: seed_item_id prefix if present else majority domain of targets
    req_domain = {}
    for r in requests:
        dom = None
        seed = r.get("seed_item_id")
        if seed and "::" in str(seed):
            dom = str(seed).split("::")[0]
        else:
            doms = [id2item.get(t, "").split("::")[0] for t in r.get("targets", [])]
            doms = [d for d in doms if d]
            if doms:
                dom = Counter(doms).most_common(1)[0][0]
        if r.get("user_idx") is not None:
            req_domain[r["user_idx"]] = dom
    eval_users = sorted(u for u in req_domain if u is not None)
    print(f"requests={len(requests)} unique_eval_users={len(eval_users)}", flush=True)

    train = pd.read_parquet(SPLITS / "train.parquet",
                            columns=["user_idx", "item_idx", "domain", "rating"])
    hist = train[train.user_idx.isin(eval_users)]
    print(f"history rows for eval users: {len(hist):,}", flush=True)

    # per-user domain distribution
    report = {"method": "train.parquet filtered to campaign_005 eval user_idx; "
              "request domain = seed_item_id prefix else majority target domain; "
              "pollution = history rows whose domain != request domain",
              "n_eval_users": len(eval_users), "n_requests": len(requests)}

    user_dom_counts = hist.groupby(["user_idx", "domain"]).size().unstack(fill_value=0)
    multi_users = user_dom_counts[(user_dom_counts > 0).sum(axis=1) > 1]
    report["eval_users_with_multi_domain_history"] = int(len(multi_users))
    report["pct_eval_users_multi_domain_history"] = round(
        100 * len(multi_users) / len(eval_users), 1)

    # per-request pollution: for each request, share of that user's history
    # outside the request domain
    poll = []
    tgt_dom_minority = 0
    n_with_hist = 0
    for r in requests:
        u = r["user_idx"]; rd = req_domain.get(u)
        if rd is None:
            continue
        sub = hist[hist.user_idx == u]
        if len(sub) == 0:
            continue
        n_with_hist += 1
        out = int((sub.domain != rd).sum())
        poll.append({"request_id": r["request_id"], "kind": r["kind"],
                     "user_idx": int(u), "request_domain": rd,
                     "history_n": int(len(sub)), "outside_domain_n": out,
                     "outside_domain_pct": round(100 * out / len(sub), 1)})
        # target domains vs majority history domain
        tdoms = [id2item.get(t, "").split("::")[0] for t in r.get("targets", [])]
        tdoms = [d for d in tdoms if d]
        if tdoms:
            maj = sub.domain.value_counts().idxmax()
            if Counter(tdoms).most_common(1)[0][0] != maj:
                tgt_dom_minority += 1
    report["requests_with_history"] = n_with_hist
    report["mean_outside_domain_pct"] = round(
        float(np.mean([p["outside_domain_pct"] for p in poll])), 2) if poll else None
    report["median_outside_domain_pct"] = round(
        float(np.median([p["outside_domain_pct"] for p in poll])), 2) if poll else None
    report["pct_requests_majority_history_outside_request_domain"] = round(
        100 * sum(1 for p in poll if p["outside_domain_n"] > p["history_n"] / 2)
        / len(poll), 1) if poll else None
    report["requests_where_target_domain_is_minority_history_domain"] = int(tgt_dom_minority)
    report["pollution_examples"] = sorted(poll, key=lambda x: -x["outside_domain_pct"])[:5]
    report["clean_examples"] = sorted(poll, key=lambda x: x["outside_domain_pct"])[:3]

    # rating-scale sanity per domain (weak collision signal)
    rating_by_dom = hist.groupby("domain")["rating"].agg(["mean", "std", "count"])
    report["rating_stats_by_domain"] = {
        d: {"mean": round(float(v["mean"]), 3), "std": round(float(v["std"]), 3),
            "n": int(v["count"])} for d, v in rating_by_dom.iterrows()}

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                   encoding="utf-8")
    print("wrote", OUT, flush=True)
    print(json.dumps({k: v for k, v in report.items()
                      if k != "pollution_examples" and k != "clean_examples"},
                     indent=1, default=str)[:2500])


if __name__ == "__main__":
    main()
