"""Protocol-difficulty emulation: literature candidate-pool protocols vs our
full-catalog held-out-target protocol, run offline on campaign_005 exp_5 data.

READ-ONLY w.r.t. project code: only reads splits/corpus/requests and writes
results JSON next to this script.

Data anchors (same as run_agent_eval, eval_on=validation):
  - fit split  = resource/splits/multi_domain/train.parquet
                 (popularity = per-item interaction count in fit split,
                 causal pre-as_of — same proxy as dc100d1 / temp.item_popularity)
  - targets    = requests.jsonl of campaign_005 exp_5 (196 held-out targets,
                 as_of = 1617737606549)
  - universe   = corpus items with first_seen_ts <= as_of (visibility gate)

Emulated protocols (per target, S seeds):
  pool10_uniform / pool20_uniform / pool100_uniform : 1 positive + (N-1)
      uniform negatives over the visible universe
  pool10_popneg / pool100_popneg                    : negatives sampled prop. to
      fit interaction count (zero-count items never drawn)
  pool10_catneg / pool100_catneg                    : negatives from the
      target's deepest category (fallback uniform if too few)
  full_catalog                                      : rank the whole visible
      universe (~2.0M items)

Baselines under every protocol: random, popularity (causal fit count,
item_idx tiebreak), same_category_as_history (user's majority deepest
category over fit history first, then popularity).

Metrics: HR@k, Recall@k, NDCG@k for k in {1,3,5,10,20} (k <= pool size),
evaluated per request (matching run_agent_eval) with fit-history items
excluded, and aggregated as mean ± std across seeds.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from bisect import bisect_left
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "protocol_emulation_results.json"

REQS = ROOT / "experiments/agent_eval/campaigns/campaign_005" \
    / "exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True" \
    / "run_1/requests.jsonl"
ITEM2ID = ROOT / "resource/mapped/multi_domain/item2id.json"
TRAIN = ROOT / "resource/splits/multi_domain/train.parquet"
DB = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
AS_OF = 1617737606549
SEEDS = list(range(5))
KS = (1, 3, 5, 10, 20)


def metrics_from_positions(positions: list[int], ks: tuple[int, ...]) -> dict[str, float]:
    """positions = 0-based ranks of all relevant targets for one request."""
    m = len(positions)
    out = {}
    for k in ks:
        hits = [p for p in positions if p < k]
        out[f"HR@{k}"] = float(len(hits) > 0)
        out[f"Recall@{k}"] = float(len(hits) / m)
        dcg = sum(1.0 / np.log2(p + 2) for p in hits)
        idcg = sum(1.0 / np.log2(i + 2) for i in range(min(m, k)))
        out[f"NDCG@{k}"] = float(dcg / idcg) if idcg > 0 else 0.0
    return out


def agg(rows_by_seed: list[list[dict]]) -> dict[str, dict[str, float]]:
    """Aggregate per-seed means first, then report mean ± std across seeds."""
    keys = rows_by_seed[0][0].keys()
    out = {}
    for k in keys:
        seed_means = [float(np.mean([r[k] for r in seed_rows])) for seed_rows in rows_by_seed]
        out[k] = {
            "mean": float(np.mean(seed_means)),
            "std": float(np.std(seed_means)),
        }
    return out


def main() -> None:
    # ---------- load mappings / requests ----------
    item2id = json.loads(ITEM2ID.read_text(encoding="utf-8"))
    idx2name = {v: k for k, v in item2id.items()}
    name2idx = item2id
    num_items = len(item2id)

    requests = [json.loads(l) for l in open(REQS, encoding="utf-8")]
    cases = []
    for r in requests:
        targets = [int(t) for t in r.get("targets", []) if t in idx2name]
        if targets:
            cases.append({
                "request_id": r["request_id"],
                "user_idx": r["user_idx"],
                "targets": targets,
            })
    print(f"requests with targets: {len(cases)} (total targets: {sum(len(c['targets']) for c in cases)})", flush=True)

    # ---------- corpus: visible universe + categories ----------
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    vis_names = [r[0] for r in conn.execute(
        "SELECT item_id FROM items WHERE first_seen_ts <= ?", (AS_OF,))]
    # deepest category = last row per item (browse-path order, root -> leaf)
    cat_map: dict[str, str] = {}
    cur_item, cur_cat = None, None
    for iid, cat in conn.execute(
            "SELECT item_id, category FROM item_categories ORDER BY item_id, rowid"):
        if iid != cur_item:
            cur_item, cur_cat = iid, cat
        else:
            cur_cat = cat
        cat_map[cur_item] = cur_cat
    conn.close()
    print(f"visible items: {len(vis_names)}  with category: {len(cat_map)}", flush=True)

    univ_idx = np.array([name2idx[n] for n in vis_names if n in name2idx],
                        dtype=np.int64)
    N = len(univ_idx)
    print(f"universe (mapped): {N}", flush=True)

    # deepest-category code per universe item (-1 = no category)
    cat_code: dict[str, int] = {}
    univ_cat = np.empty(N, dtype=np.int64)
    for p, i in enumerate(univ_idx):
        c = cat_map.get(idx2name[int(i)])
        if c is None:
            univ_cat[p] = -1
        else:
            if c not in cat_code:
                cat_code[c] = len(cat_code)
            univ_cat[p] = cat_code[c]
    code2cat = {v: k for k, v in cat_code.items()}

    # ---------- fit split: popularity + user histories ----------
    fit = pd.read_parquet(TRAIN, columns=["user_idx", "item_idx", "timestamp"])
    print(f"fit rows: {len(fit)}", flush=True)
    pop = np.zeros(num_items, dtype=np.int64)
    vc = fit["item_idx"].value_counts()
    pop[vc.index.to_numpy()] = vc.to_numpy()
    need_users = {c["user_idx"] for c in cases}
    hist = (fit[fit["user_idx"].isin(need_users)]
            .sort_values("timestamp")
            .groupby("user_idx")
            .apply(lambda g: list(zip(g["timestamp"], g["item_idx"])),
                   include_groups=False)
            .to_dict())
    print(f"users with history loaded: {len(hist)}", flush=True)

    def cat_of_idx(item_idx: int) -> str | None:
        return cat_map.get(idx2name.get(int(item_idx), ""))

    # user majority category: most frequent deepest cat over fit history;
    # ties -> category of the most recent item that has one.
    user_cat: dict[int, str | None] = {}
    for u, rows_ in hist.items():
        cnt = Counter()
        for _, it in rows_:
            c = cat_of_idx(it)
            if c:
                cnt[c] += 1
        if not cnt:
            user_cat[u] = None
            continue
        best = max(cnt.values())
        tied = [c for c, n in cnt.items() if n == best]
        if len(tied) == 1:
            user_cat[u] = tied[0]
        else:
            user_cat[u] = next((cat_of_idx(it) for _, it in reversed(rows_)
                                if cat_of_idx(it) in tied), tied[0])

    user_hist_items: dict[int, set[int]] = {
        u: {int(it) for _, it in rows_} for u, rows_ in hist.items()
    }
    target_cats = {
        t: cat_of_idx(t) for c in cases for t in c["targets"]
    }

    # ---------- fast negative samplers ----------
    # Precompute popularity CDF over universe once (weights are seed-invariant).
    w_univ = pop[univ_idx].astype(np.float64)
    w_sum = w_univ.sum()
    pop_cdf = np.cumsum(w_univ) / w_sum if w_sum > 0 else None

    cat_members: dict[str | None, np.ndarray] = {}

    def members_of(cat: str | None) -> np.ndarray:
        if cat not in cat_members:
            code = cat_code.get(cat) if cat is not None else None
            mem = univ_idx[univ_cat == code] if code is not None else \
                np.empty(0, dtype=np.int64)
            cat_members[cat] = mem
        return cat_members[cat]

    def draw_uniform(n: int, rng: np.random.Generator,
                     exclude: set[int] | None = None) -> np.ndarray:
        """n distinct positions in univ_idx via rejection (collisions ~0)."""
        seen = set(exclude) if exclude else set()
        res = []
        while len(res) < n:
            out = rng.integers(0, N, size=(n - len(res)) * 2)
            for it in univ_idx[out]:
                i = int(it)
                if i not in seen:
                    seen.add(i)
                    res.append(i)
                    if len(res) == n:
                        return np.array(res, dtype=np.int64)
        return np.array(res, dtype=np.int64)

    def draw_popneg(n: int, rng: np.random.Generator,
                    exclude: set[int] | None = None) -> np.ndarray:
        if pop_cdf is None:
            return draw_uniform(n, rng, exclude=exclude)
        res, seen = [], (set(exclude) if exclude else set())
        while len(res) < n:
            u = rng.random((n - len(res)) * 3)
            pos = np.searchsorted(pop_cdf, u)
            pos = np.clip(pos, 0, N - 1)
            for it in univ_idx[pos]:
                i = int(it)
                if pop[i] > 0 and i not in seen:
                    seen.add(i)
                    res.append(i)
                    if len(res) == n:
                        return np.array(res, dtype=np.int64)
        return np.array(res, dtype=np.int64)

    def draw_catneg(targets: list[int], n: int,
                    rng: np.random.Generator,
                    exclude: set[int]) -> np.ndarray:
        # Pool negatives from the categories of the request's targets.
        avail_set: list[int] = []
        seen_avail: set[int] = set()
        for t in targets:
            tcat = target_cats.get(t)
            for x in members_of(tcat):
                xi = int(x)
                if xi not in exclude and xi not in seen_avail:
                    seen_avail.add(xi)
                    avail_set.append(xi)
        take = min(n, len(avail_set))
        out = []
        if take:
            sel = rng.choice(len(avail_set), size=take, replace=False)
            out = [avail_set[i] for i in sel]
        if take < n:
            out.extend(draw_uniform(n - take, rng, exclude=exclude | set(out)).tolist())
        return np.array(out[:n], dtype=np.int64)

    # ---------- pool protocol ----------
    def pool_protocol(pool_size: int, variant: str) -> dict:
        ks = tuple(k for k in KS if k <= pool_size)
        samplers = {"uniform": draw_uniform, "popneg": draw_popneg}
        rows_by_seed = {b: [] for b in ("random", "popularity", "same_category")}
        for seed in SEEDS:
            rng = np.random.default_rng(1000 + seed)
            seed_rows = {b: [] for b in ("random", "popularity", "same_category")}
            for c in cases:
                targets = c["targets"]
                m = len(targets)
                u_hist = user_hist_items.get(c["user_idx"], set())
                exclude = u_hist | set(targets)
                n_neg = max(0, pool_size - m)
                if variant == "catneg":
                    neg = draw_catneg(targets, n_neg, rng, exclude)
                else:
                    neg = samplers[variant](n_neg, rng, exclude=exclude)
                pool = np.concatenate([np.array(targets, dtype=np.int64), neg])
                p_len = len(pool)
                C = user_cat.get(c["user_idx"])
                # random: perm[j] = pool index at rank j; targets are indices 0..m-1
                perm = rng.permutation(p_len)
                pos_map = {int(perm[j]): j for j in range(p_len)}
                seed_rows["random"].append(
                    metrics_from_positions([pos_map[idx] for idx in range(m)], ks))
                # popularity: (-pop, idx)
                order = sorted(range(p_len),
                               key=lambda i: (-int(pop[pool[i]]), int(pool[i])))
                rank_in_order = {idx: r for r, idx in enumerate(order)}
                seed_rows["popularity"].append(
                    metrics_from_positions([rank_in_order[idx] for idx in range(m)], ks))
                # same_category: cat==C first, then popularity
                order = sorted(
                    range(p_len),
                    key=lambda i: (0 if C is not None
                                   and cat_of_idx(int(pool[i])) == C else 1,
                                   -int(pop[pool[i]]), int(pool[i])))
                rank_in_order = {idx: r for r, idx in enumerate(order)}
                seed_rows["same_category"].append(
                    metrics_from_positions([rank_in_order[idx] for idx in range(m)], ks))
            for b in rows_by_seed:
                rows_by_seed[b].append(seed_rows[b])
        return {b: agg(v) for b, v in rows_by_seed.items()}

    # ---------- full-catalog protocol ----------
    def full_catalog_protocol() -> dict:
        rows_by_seed = {b: [] for b in ("random", "popularity", "same_category")}
        # deterministic popularity order: pop desc, item_idx asc
        order = np.lexsort((univ_idx, -pop[univ_idx]))
        sorted_items = univ_idx[order]
        rank_of = {int(i): r for r, i in enumerate(sorted_items)}
        cat_sorted: dict[str, tuple[np.ndarray, list]] = {}

        def cat_sorted_keys(cat: str):
            if cat not in cat_sorted:
                mem = members_of(cat)
                o = np.lexsort((mem, -pop[mem]))
                mem_s = mem[o]
                cat_sorted[cat] = (mem_s,
                                   [(-int(pop[i]), int(i)) for i in mem_s])
            return cat_sorted[cat]

        for seed in SEEDS:
            rng = np.random.default_rng(2000 + seed)
            seed_rows = {b: [] for b in ("random", "popularity", "same_category")}
            for c in cases:
                targets = c["targets"]
                u_hist = user_hist_items.get(c["user_idx"], set())
                hist_in_univ = [h for h in u_hist if h in rank_of]
                n_avail = max(1, N - len(hist_in_univ))
                C = user_cat.get(c["user_idx"])

                # random: distinct positions in [0, n_avail)
                rand_pos = rng.choice(n_avail, size=min(len(targets), n_avail), replace=False).tolist()
                if len(rand_pos) < len(targets):
                    rand_pos.extend([n_avail] * (len(targets) - len(rand_pos)))
                seed_rows["random"].append(metrics_from_positions(rand_pos, KS))

                # popularity (excluding fit history)
                pop_positions = []
                for t in targets:
                    if t not in rank_of:
                        pop_positions.append(N)
                    else:
                        r = rank_of[t]
                        hist_above = sum(1 for h in hist_in_univ if rank_of[h] < r)
                        pop_positions.append(r - hist_above)
                seed_rows["popularity"].append(metrics_from_positions(pop_positions, KS))

                # same_category (excluding fit history)
                if C is None:
                    cat_positions = pop_positions
                else:
                    mem_s, keys = cat_sorted_keys(C)
                    nC = len(mem_s)
                    hist_in_C = [h for h in hist_in_univ if cat_of_idx(h) == C]
                    hist_out_C = [h for h in hist_in_univ if cat_of_idx(h) != C]
                    nC_avail = nC - len(hist_in_C)
                    cat_positions = []
                    for t in targets:
                        if t not in rank_of:
                            cat_positions.append(N)
                            continue
                        r = rank_of[t]
                        c_above = bisect_left(keys, (-int(pop[t]), int(t)))
                        if target_cats.get(t) == C:
                            hist_c_above = sum(1 for h in hist_in_C if rank_of[h] < r)
                            cat_positions.append(c_above - hist_c_above)
                        else:
                            hist_out_above = sum(1 for h in hist_out_C if rank_of[h] < r)
                            cat_positions.append(nC_avail + max(0, (r - c_above) - hist_out_above))
                seed_rows["same_category"].append(metrics_from_positions(cat_positions, KS))
            for b in rows_by_seed:
                rows_by_seed[b].append(seed_rows[b])
        return {b: agg(v) for b, v in rows_by_seed.items()}

    # ---------- run ----------
    results = {"meta": {
        "as_of": AS_OF, "seeds": SEEDS,
        "n_requests": len(cases),
        "n_targets": sum(len(c["targets"]) for c in cases),
        "universe_size": N, "fit_rows": int(len(fit)),
        "history_excluded": True,
        "std_semantics": "std across seeds (per-seed request-level mean)",
        "popularity": "fit-split (train.parquet) interaction count per item_idx "
                      "(causal, same proxy as dc100d1 temp.item_popularity)",
        "universe": "items.first_seen_ts <= as_of",
        "same_category": "user majority deepest category over fit history; "
                         "items in that category ranked first by popularity",
        "note": "deterministic baselines have std=0; random/popneg/catneg vary by seed",
    }, "protocols": {}}

    for name, ps, var in [
        ("pool10_uniform", 10, "uniform"),
        ("pool20_uniform", 20, "uniform"),
        ("pool100_uniform", 100, "uniform"),
        ("pool10_popneg", 10, "popneg"),
        ("pool100_popneg", 100, "popneg"),
        ("pool10_catneg", 10, "catneg"),
        ("pool100_catneg", 100, "catneg"),
    ]:
        print(f"running {name} ...", flush=True)
        results["protocols"][name] = pool_protocol(ps, var)

    print("running full_catalog ...", flush=True)
    results["protocols"]["full_catalog"] = full_catalog_protocol()

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("wrote", OUT)

    for pname, prot in results["protocols"].items():
        print(f"\n== {pname} ==")
        for b, mets in prot.items():
            line = f"  {b:14s}"
            for k in ("HR@1", "Recall@5", "Recall@10", "NDCG@10"):
                if k in mets:
                    line += f" {k}={mets[k]['mean']:.4f}±{mets[k]['std']:.4f}"
            print(line)


if __name__ == "__main__":
    main()
