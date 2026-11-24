"""Q6: offline scorer comparison on injected targets (rescue@10).

Same setup as ranktool_injection_probe / §6.7: for each campaign_005 exp_5
request, take the union of recorded retrieval candidates, append held-out
targets LAST, re-score with variant scorers, measure target rank.

Eligible targets = fate 'ranked' in ranktool_injection_exp5.json AND request
had non-empty retrieval union (real competition) — same conditioning as §6.7.

Retrieval features per candidate (per leg = one ok retrieval step):
  - leg rank = position in that step's candidate list (1-based)
  - leg score = candidate['score'] (SearchTool) | ['similarity'] (SimilarTool)
                | MISSING for FilterTool -> handled as rank-only:
                normalized leg score = 1 - (rank-1)/n_leg  (stated handling)
  - retr_norm  = max over legs of per-leg min-max-normalized score
                 (per-leg normalization because BM25/similarity/pop-rank are
                 incomparable across tools)
  - rrf        = sum over legs of 1/(60 + rank)
  - leg_count  = # distinct tools returning the item
  - cat_match  = item shares >=1 category with seed_item_id (similar) or
                 request 'category' field, else any history-item category
  - pop_norm   = scorer._pop_norm (pre-target popularity / peak)
  - cf         = user_items @ similarity column (ItemKNN CF term)

Variants:
  v1a baseline_exact : cf + 1e-6*pop   (reproduces §6.7 BaselineScorer)
  v1b pop_only       : pop_norm
  v2  linear_blend   : minmax(retr)+minmax(pop)+minmax(cf) per request
  v3  rrf_legs       : rrf + 1e-6*pop
  v4  blend_extras   : v2 + 0.1*(leg_count-1) + 0.2*cat_match
  v5  learned        : logistic regression (numpy GD) on
                       [retr,pop,cf,leg_count,cat_match,rrf], 5-fold CV by request

Output: investigations/q6_scorer_comparison.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "evaluation"))
sys.path.insert(0, str(ROOT))

from ranktool_score_audit import build_scorer, _load_jsonl  # noqa: E402

RUN = ROOT / "experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1"
INJ = ROOT / "investigations" / "ranktool_injection_exp5.json"
DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
OUT = Path(__file__).parent / "q6_scorer_comparison.json"
RETRIEVAL_TOOLS = ("SearchTool", "FilterTool", "SimilarTool")
RRF_K = 60


def minmax(a: np.ndarray) -> np.ndarray:
    lo, hi = a.min(), a.max()
    return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)


def main() -> None:
    scorer, user2id, item2id, mode = build_scorer("validation")
    print(f"scorer mode={mode}", flush=True)
    id2item = {v: k for k, v in item2id.items()}
    n_items = scorer.num_items

    requests = {r["request_id"]: r for r in _load_jsonl(RUN / "requests.jsonl")}
    traj_path = RUN / "trajectories.jsonl"
    if not traj_path.exists():
        traj_path = next(RUN.glob("*trajectories.jsonl"))
    inj = json.loads(INJ.read_text(encoding="utf-8"))[0]
    inj_by_req = {r["request_id"]: r for r in inj["per_request"]}

    # ---- pass 1: build per-request candidate feature rows ----
    rows = []          # feature dicts
    req_meta = []      # (request_id, kind, user_idx, target_idxs, eligible_target_names)
    all_cat_ids = set()
    user_hist_items: dict[int, list[int]] = {}

    for row in _load_jsonl(traj_path):
        req = requests.get(row.get("request_id"))
        if req is None:
            continue
        targets = [id2item[i] for i in req.get("targets", []) if i in id2item]
        if not targets:
            continue
        rid = row["request_id"]
        kind = req.get("kind") or "?"
        user_id = req["user_id"]
        user_idx = user2id.get(user_id, -1)

        # per-leg candidate lists: leg -> [(item_id, rank, score_or_None)]
        legs: dict[str, list[tuple[str, int, float | None]]] = defaultdict(list)
        union_order: list[str] = []
        seen: set[str] = set()
        for step in row.get("steps", []):
            if step.get("tool") not in RETRIEVAL_TOOLS or not step.get("ok"):
                continue
            tool = step["tool"]
            cands = (step.get("data") or {}).get("candidates") or []
            for rank, c in enumerate(cands, 1):
                iid = c.get("item_id")
                if not iid:
                    continue
                score = c.get("score")
                if score is None:
                    score = c.get("similarity")
                legs[f"{rid}|{tool}|{len(legs)}"].append((iid, rank, score))
                # leg key must distinguish multiple calls of same tool:
                if iid not in seen:
                    seen.add(iid)
                    union_order.append(iid)
        # rebuild legs keyed properly (the f-string above collapses same-tool steps)
        legs = defaultdict(list)
        for step in row.get("steps", []):
            if step.get("tool") not in RETRIEVAL_TOOLS or not step.get("ok"):
                continue
            tool = step["tool"]
            cands = (step.get("data") or {}).get("candidates") or []
            for rank, c in enumerate(cands, 1):
                iid = c.get("item_id")
                if not iid:
                    continue
                score = c.get("score")
                if score is None:
                    score = c.get("similarity")
                legs[tool].append((iid, rank, score))  # per-tool merge; rank restarts per call approx
        injected = [t for t in targets if t not in seen]
        combined = union_order + injected
        if not combined:
            continue

        # eligible targets per injection json
        ireq = inj_by_req.get(rid, {})
        fates = ireq.get("fates", {})
        eligible = {t for t, f in
                    ((t, fates.get(t)) for t in targets)}  # placeholder, refined below

        # scorer terms
        idxs = np.array([item2id.get(c, -1) for c in combined], dtype=np.int64)
        valid = (idxs >= 0) & (idxs < n_items)
        safe = np.clip(idxs, 0, n_items - 1)
        pop = scorer._pop_norm[safe]
        cf = np.zeros(len(combined))
        if scorer.similarity is not None and scorer.is_known_user(user_idx):
            cf_row = (scorer.user_items.getrow(user_idx) @ scorer.similarity).tocsr()
            cf = cf_row[:, safe].toarray().ravel().astype(np.float64)
            cf[~valid] = 0.0
        base = cf + pop * 1e-6  # BaselineScorer exact
        pure_pop = pop.copy()

        # per-candidate leg features
        item_legs: dict[str, list[tuple[str, int, float | None]]] = defaultdict(list)
        for tool, lst in legs.items():
            for iid, rank, score in lst:
                item_legs[iid].append((tool, rank, score))

        n_by_tool = {t: len(lst) for t, lst in legs.items()}
        retr = np.zeros(len(combined))
        rrf = np.zeros(len(combined))
        leg_count = np.zeros(len(combined))
        for j, cid in enumerate(combined):
            ls = item_legs.get(cid, [])
            leg_count[j] = len({t for t, _, _ in ls})
            best = 0.0
            for tool, rank, score in ls:
                n_leg = n_by_tool[tool]
                if score is None:
                    sn = 1.0 - (rank - 1) / max(n_leg, 1)  # FilterTool: rank-only handling
                else:
                    # per-leg min-max of scores within this leg's list
                    scores_all = [s for _, _, s in legs[tool] if s is not None]
                    lo, hi = (min(scores_all), max(scores_all)) if scores_all else (0, 0)
                    sn = (score - lo) / (hi - lo) if hi > lo else 1.0
                best = max(best, sn)
                rrf[j] += 1.0 / (RRF_K + rank)
            retr[j] = best

        retr_n = minmax(retr)
        pop_n = minmax(pop)
        cf_n = minmax(cf)
        lc_n = minmax(leg_count)

        # category affinity placeholder filled after sqlite pass
        target_set = set(targets)
        for j, cid in enumerate(combined):
            rows.append({
                "request_id": rid, "kind": kind, "user_idx": user_idx,
                "item_id": cid, "is_target": cid in target_set,
                "retr": float(retr_n[j]), "pop": float(pop_n[j]), "cf": float(cf_n[j]),
                "leg_count": float(leg_count[j]), "rrf": float(rrf[j]),
                "base": float(base[j]), "pure_pop": float(pure_pop[j]),
            })
            all_cat_ids.add(cid)
        # history items for cat affinity
        if user_idx >= 0:
            hist = scorer.user_items.getrow(user_idx).indices
            user_hist_items[user_idx] = [int(x) for x in hist if 0 <= x < n_items]
        # eligible target names: fate=='ranked' from injection probe
        ranked_targets = {t for t in targets
                          if (inj_by_req.get(rid, {}).get("target_ranks") or {}).get(t) is not None}
        req_meta.append({
            "request_id": rid, "kind": kind, "user_idx": user_idx,
            "targets": targets, "eligible": sorted(ranked_targets),
            "n_union": len(union_order),
            "request": req,
        })
        all_cat_ids.update(id2item.get(h, "") for h in user_hist_items.get(user_idx, []))
    print(f"requests={len(req_meta)} candidate rows={len(rows)}", flush=True)

    # ---- pass 2: category affinity via sqlite ----
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    needed = sorted(i for i in all_cat_ids if i)
    cat_map: dict[str, set[str]] = defaultdict(set)
    for k in range(0, len(needed), 400):
        chunk = needed[k:k + 400]
        marks = ",".join("?" * len(chunk))
        for iid, cat in conn.execute(
                f"SELECT item_id, category FROM item_categories WHERE item_id IN ({marks})", chunk):
            cat_map[iid].add(cat)

    # per-request reference category set
    ref_cats: dict[str, set[str]] = {}
    hist_cat_cache: dict[int, set[str]] = {}
    for m in req_meta:
        req = m["request"]
        ref: set[str] = set()
        if req.get("category"):
            ref |= cat_map.get(req["category"], set()) if isinstance(req.get("category"), str) else set()
            # request.category may itself be a category name or item id
            if req["category"] in cat_map:
                ref |= cat_map[req["category"]]
        if req.get("seed_item_id"):
            ref |= cat_map.get(req["seed_item_id"], set())
        if not ref:
            uidx = m["user_idx"]
            if uidx not in hist_cat_cache:
                hc: set[str] = set()
                for h in user_hist_items.get(uidx, []):
                    hc |= cat_map.get(id2item.get(h, ""), set())
                hist_cat_cache[uidx] = hc
            ref = hist_cat_cache[uidx]
        ref_cats[m["request_id"]] = ref

    for r in rows:
        ref = ref_cats.get(r["request_id"], set())
        r["cat_match"] = 1.0 if (cat_map.get(r["item_id"], set()) & ref) else 0.0
    print("categories done", flush=True)

    df = pd.DataFrame(rows)
    # variant scores
    df["v1a"] = df["base"]
    df["v1b"] = df["pure_pop"]
    df["v2"] = df["retr"] + df["pop"] + df["cf"]
    df["v3"] = df["rrf"] + df["pop"] * 1e-6
    df["v4"] = df["v2"] + 0.1 * (df["leg_count"] - 1).clip(lower=0) + 0.2 * df["cat_match"]

    # ---- v5 learned reranker: logistic regression, 5-fold by request ----
    feat_cols = ["retr", "pop", "cf", "leg_count", "cat_match", "rrf"]
    X = df[feat_cols].to_numpy(np.float64)
    y = df["is_target"].to_numpy(np.float64)
    req_ids = df["request_id"].to_numpy()
    uniq_reqs = np.array(sorted(set(req_ids)))
    rng = np.random.default_rng(42)
    fold_of = {r: i % 5 for i, r in enumerate(rng.permutation(uniq_reqs))}
    df["fold"] = [fold_of[r] for r in req_ids]
    pred = np.zeros(len(df))
    for fold in range(5):
        tr = df["fold"].to_numpy() != fold
        te = ~tr
        # standardize on train
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        Xs = (X - mu) / sd
        w = np.zeros(X.shape[1] + 1)
        Xb = np.hstack([Xs, np.ones((len(Xs), 1))])
        # weighted BCE (pos_weight ~ neg/pos) plain GD
        yt = y[tr]
        pw = (1 - yt).sum() / max(yt.sum(), 1)
        for _ in range(300):
            z = Xb[tr] @ w
            p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
            wt = np.where(yt > 0, pw, 1.0)
            grad = (Xb[tr].T @ ((p - yt) * wt)) / wt.sum() + 1e-3 * w
            w -= 0.5 * grad
        pred[te] = 1 / (1 + np.exp(-np.clip(Xb[te] @ w, -30, 30)))
    df["v5"] = pred
    print("learned reranker done", flush=True)

    # ---- rescue@10 per variant ----
    variants = ["v1a", "v1b", "v2", "v3", "v4", "v5"]
    eligible = [(m["request_id"], t) for m in req_meta for t in m["eligible"]]
    result = {"n_requests": len(req_meta), "n_eligible_targets": len(eligible),
              "variants": {}, "per_kind": {}}
    # rank targets within each request by variant score desc, tie -> union order (stable)
    df["_order"] = np.arange(len(df))
    for v in variants:
        hits10 = 0
        hits20 = 0
        ranks_all = []
        for m in req_meta:
            sub = df[df.request_id == m["request_id"]]
            order = sub.sort_values([v, "_order"], ascending=[False, True])
            rank_of = {iid: r for r, iid in enumerate(order.item_id, 1)}
            for t in m["eligible"]:
                rk = rank_of.get(t)
                if rk is not None:
                    ranks_all.append(rk)
                    if rk <= 10:
                        hits10 += 1
                    if rk <= 20:
                        hits20 += 1
        result["variants"][v] = {
            "rescue@10": f"{hits10}/{len(eligible)} = {hits10/len(eligible):.4f}",
            "rescue@20": f"{hits20}/{len(eligible)} = {hits20/len(eligible):.4f}",
            "median_rank": float(np.median(ranks_all)) if ranks_all else None,
        }
        print(v, result["variants"][v], flush=True)

    # per-kind for v1a/v5
    for v in ("v1a", "v5"):
        pk = defaultdict(lambda: [0, 0])
        for m in req_meta:
            sub = df[df.request_id == m["request_id"]]
            order = sub.sort_values([v, "_order"], ascending=[False, True])
            rank_of = {iid: r for r, iid in enumerate(order.item_id, 1)}
            for t in m["eligible"]:
                rk = rank_of.get(t)
                pk[m["kind"]][1] += 1
                if rk is not None and rk <= 10:
                    pk[m["kind"]][0] += 1
        result["per_kind"][v] = {k: f"{a}/{b} = {a/b:.3f}" for k, (a, b) in pk.items()}

    # feature-target stats
    result["feature_target_means"] = {
        c: {"target": float(df[df.is_target][c].mean()),
            "nontarget": float(df[~df.is_target][c].mean())}
        for c in ["retr", "pop", "cf", "leg_count", "cat_match", "rrf"]}
    df.to_parquet(OUT.with_suffix(".features.parquet"))
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["variants"], indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
