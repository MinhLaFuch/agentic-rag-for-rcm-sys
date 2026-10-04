"""
Candidate recall: do the retrieval tools put the held-out items in front of the reranker?

For each sampled validation (or test) user we ask every candidate source for N items, drop the
items the user already has in the fit data, and check how many of the user's held-out items
appear.  Nothing here uses an LLM; it answers "is retrieval the bottleneck?" before any
reranking or agent work.

Sources
  popularity   global top-N by train count               (works for everyone, incl. cold)
  item_cf      ItemCFTool seeded with the user's recent items   (needs history)
  semantic     SemanticSearchTool, query built as below         (needs a query)
  union        all three, merged round-robin to N (budget-matched) and plain union (larger)

Where the semantic query comes from (there are no real user queries offline, so it is simulated):
  history          titles of the user's last few fit items.       Honest, but empty for cold users.
  category_oracle  categories of the user's held-out items.       Simulates "I want a <category>";
                   an UPPER BOUND that leaks target information - never report it as a result.

Segments follow the evaluator: cold = 0 fit interactions, sparse = 1..sparse_max, warm = more.

    python scripts/candidate_recall.py \
        --splits-dir data/splits/Video_Games --mapping-dir data/mapped/Video_Games \
        --meta Video_Games=data/raw/Video_Games/meta_Video_Games.jsonl.gz
"""

from __future__ import annotations

import argparse
import time
from itertools import islice
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from package.config.loader import load_config
from package.data import ITEM_ID_SEPARATOR, namespaced_item_id
from package.data.loader import iter_jsonl_gz
from package.data.mapping import load_mappings
from package.tools import ItemCFTool, ItemCorpus, SemanticSearchTool
from package.tools.base import MAX_CANDIDATES, ToolCallLogger
from package.tools.evaluation.experiment_log import next_experiment_dir, save_experiment
from package.tools.recommenders import ItemKNNRecommender, build_interaction_matrix
from package.utils.console import ensure_utf8_stdout

META_FIELDS = ["parent_asin", "title", "store", "price", "average_rating", "rating_number", "main_category", "categories"]
SEGMENTS = ("cold", "sparse", "warm")
SOURCES = ("popularity", "item_cf", "semantic", "union_rr", "union_all")


# ----------------------------------------------------------------------------- data


def load_meta(meta_args: list[tuple[str, str]], item2id: dict[str, int], namespaced: bool) -> pd.DataFrame:
    """Metadata rows for items that exist in the mapping (same key rule as the splits)."""
    frames = []
    for domain, path in meta_args:
        rows = []
        for rec in iter_jsonl_gz(path):
            asin = rec.get("parent_asin")
            key = namespaced_item_id(domain, asin) if namespaced else asin
            if key in item2id:
                rows.append({k: rec.get(k) for k in META_FIELDS})
        df = pd.DataFrame(rows, columns=META_FIELDS)
        df["domain"] = domain
        print(f"  {domain}: kept {len(df):,} items with metadata")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def item_text_tables(meta: pd.DataFrame, item2id: dict[str, int], namespaced: bool):
    """item_idx -> title, and item_idx -> category words (used to simulate queries)."""
    title, cats = {}, {}
    for r in meta.itertuples(index=False):
        key = namespaced_item_id(r.domain, r.parent_asin) if namespaced else r.parent_asin
        idx = item2id.get(key)
        if idx is None:
            continue
        title[idx] = r.title or ""
        parts = [r.main_category] + (list(r.categories) if r.categories is not None else [])
        cats[idx] = " ".join(str(p) for p in parts if p)
    return title, cats


# ----------------------------------------------------------------------------- helpers


def round_robin(lists: list[list[int]], n: int) -> list[int]:
    """Interleave ranked lists, skipping duplicates, until n items (budget-matched union)."""
    out, seen = [], set()
    for rank in range(max((len(l) for l in lists), default=0)):
        for l in lists:
            if rank < len(l) and l[rank] not in seen:
                seen.add(l[rank])
                out.append(l[rank])
                if len(out) == n:
                    return out
    return out


def drop_seen(ranked: list[int], seen: set[int], n: int) -> list[int]:
    return [i for i in ranked if i not in seen][:n]


def sample_users(seg_of: dict[int, str], per_segment: int, rng: np.random.Generator) -> dict[str, list[int]]:
    out = {}
    for seg in SEGMENTS:
        users = [u for u, s in seg_of.items() if s == seg]
        rng.shuffle(users)
        out[seg] = users[:per_segment]
    return out


# ----------------------------------------------------------------------------- main


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits-dir", required=True)
    ap.add_argument("--mapping-dir", required=True)
    ap.add_argument("--meta", action="append", default=[], required=True, help="Domain=path/to/meta_Domain.jsonl.gz")
    ap.add_argument("--eval-on", choices=["validation", "test"], default="validation")
    ap.add_argument("--n", default="50,100,200", help="candidate budgets, comma separated")
    ap.add_argument("--per-segment", type=int, default=1000, help="max users sampled per segment")
    ap.add_argument("--seed-items", type=int, default=10, help="recent fit items used as ItemCF seeds")
    ap.add_argument("--query-items", type=int, default=3, help="recent fit items whose titles form the history query")
    ap.add_argument("--neighbors", type=int, default=20, help="ItemKNN k (match model.yaml)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--experiments-dir", default="experiments/candidate_recall")
    args = ap.parse_args()

    budgets = sorted(int(x) for x in args.n.split(","))
    n_max = max(budgets)
    sparse_max = load_config("evaluation")["segment_thresholds"]["sparse_max_history"]
    rng = np.random.default_rng(args.seed)
    t_start = time.time()

    # ---- splits, mapping, fit/target (same protocol as run_baselines.py)
    splits = Path(args.splits_dir)
    def read(name: str) -> pd.DataFrame:
        path = splits / f"{name}.parquet"
        wanted = ["user_idx", "item_idx", "timestamp"]
        return pd.read_parquet(path, columns=[c for c in wanted if c in pq.ParquetFile(path).schema.names])

    train, val, test = read("train"), read("validation"), read("test")
    fit_df, target_df = (train, val) if args.eval_on == "validation" else (pd.concat([train, val]), test)
    user2id, item2id = load_mappings(args.mapping_dir)
    id2item = {v: k for k, v in item2id.items()}
    num_users, num_items = len(user2id), len(item2id)
    namespaced = any(ITEM_ID_SEPARATOR in k for k in islice(item2id, 1000))
    print(f"item ids in mapping are {'namespaced (Domain::asin)' if namespaced else 'plain parent_asin'}")

    fit_matrix = build_interaction_matrix(fit_df, num_users, num_items)
    target_by_user = target_df.groupby("user_idx")["item_idx"].apply(set).to_dict()
    hist_size = np.diff(fit_matrix.indptr)
    seg_of = {
        u: ("cold" if hist_size[u] == 0 else "sparse" if hist_size[u] <= sparse_max else "warm") for u in target_by_user
    }
    # most-recent-first fit items per user (needs a timestamp column; falls back to file order)
    fit_sorted = fit_df.sort_values("timestamp") if "timestamp" in fit_df.columns else fit_df
    recent = fit_sorted.groupby("user_idx")["item_idx"].apply(lambda s: list(s)[::-1]).to_dict()
    seen_of = {u: set(recent.get(u, [])) for u in target_by_user}

    # ---- corpus + tools
    print("Build corpus")
    meta = load_meta([tuple(m.split("=", 1)) for m in args.meta], item2id, namespaced)
    corpus = ItemCorpus.from_dataframe(meta)
    title_of, cats_of = item_text_tables(meta, item2id, namespaced)
    coverage = len(title_of) / num_items
    print(f"  metadata covers {coverage:.1%} of mapped items")
    if coverage < 0.5:
        raise SystemExit("Less than half of mapped items have metadata: check --meta paths / id format")

    print("Fit ItemKNN on fit data")
    knn = ItemKNNRecommender(args.neighbors).fit(fit_matrix)
    item_cf = ItemCFTool(knn, item2id, logger=ToolCallLogger())
    search = SemanticSearchTool(corpus, logger=ToolCallLogger())
    pop_order = np.argsort(-np.asarray(fit_matrix.sum(axis=0)).ravel(), kind="stable").tolist()
    fit_item_seen = np.asarray(fit_matrix.sum(axis=0)).ravel() > 0

    def cand_key(c: dict) -> str:  # semantic candidates carry both id forms
        return c["item_id"] if namespaced else c["original_item_id"]

    def ask_limit(u: int) -> int:  # room for the items we will drop as already-seen
        return min(n_max + len(seen_of[u]), MAX_CANDIDATES)

    def get_item_cf(u: int) -> list[int] | None:
        seeds = [id2item[i] for i in recent.get(u, [])[: args.seed_items]]
        if not seeds:
            return None
        res = item_cf(items=seeds, top_k=ask_limit(u))
        item_cf.logger.records.clear()
        return [item2id[c["item_id"]] for c in res.data.get("candidates", [])] if res.ok else []

    def get_semantic(u: int, mode: str) -> list[int] | None:
        if mode == "history":
            query = " ".join(title_of.get(i, "") for i in recent.get(u, [])[: args.query_items])
        else:  # category_oracle
            query = " ".join(cats_of.get(i, "") for i in target_by_user[u])
        if not query.strip():
            return None
        res = search(query=query, limit=ask_limit(u))
        search.logger.records.clear()
        if not res.ok:
            return []
        return [item2id[k] for k in map(cand_key, res.data["candidates"]) if k in item2id]

    # ---- evaluate
    sampled = sample_users(seg_of, args.per_segment, rng)
    metrics: dict = {}
    for mode in ("history", "category_oracle"):
        print(f"\n=== query mode: {mode} {'(UPPER BOUND, leaks target info)' if mode != 'history' else ''}")
        metrics[mode] = {}
        for seg in SEGMENTS:
            users = sampled[seg]
            acc = {s: {n: {"recall": [], "hit": []} for n in budgets} for s in SOURCES}
            size_union, no_query = [], 0
            for u in users:
                targets, seen = target_by_user[u], seen_of[u]
                ranked = {
                    "popularity": pop_order[: ask_limit(u)],
                    "item_cf": get_item_cf(u),
                    "semantic": get_semantic(u, mode),
                }
                if ranked["item_cf"] is None and ranked["semantic"] is None:
                    no_query += 1
                for n in budgets:
                    lists = {s: drop_seen(r, seen, n) for s, r in ranked.items() if r is not None}
                    lists["union_rr"] = round_robin(list(lists.values()), n)  # budget-matched: n items
                    lists["union_all"] = list(dict.fromkeys(i for s in ranked if s in lists for i in lists[s]))  # up to 3n
                    if n == budgets[-1]:
                        size_union.append(len(lists["union_all"]))
                    for s in SOURCES:
                        got = set(lists.get(s, []))  # a source with no input counts as retrieving nothing
                        acc[s][n]["recall"].append(len(got & targets) / len(targets))
                        acc[s][n]["hit"].append(float(bool(got & targets)))
            reach = np.mean([fit_item_seen[list(target_by_user[u])].mean() for u in users]) if users else float("nan")
            metrics[mode][seg] = {
                "users": len(users),
                "users_without_any_query_or_history": no_query,
                "target_items_seen_in_fit": float(reach),
                "mean_union_all_size": float(np.mean(size_union)) if size_union else 0.0,
                **{s: {str(n): {k: float(np.mean(v)) if v else 0.0 for k, v in acc[s][n].items()} for n in budgets} for s in SOURCES},
            }
            m = metrics[mode][seg]
            print(f"[{seg}] users={m['users']} no_input={no_query} targets_seen_in_fit={reach:.2f} union_all_size~{m['mean_union_all_size']:.0f}")
            for s in SOURCES:
                print("   " + s.ljust(11) + "  ".join(f"recall@{n}={m[s][str(n)]['recall']:.3f} hit@{n}={m[s][str(n)]['hit']:.3f}" for n in budgets))

    exp_dir = save_experiment(
        next_experiment_dir(args.experiments_dir),
        config={"budgets": budgets, "per_segment": args.per_segment, "seed_items": args.seed_items,
                "query_items": args.query_items, "neighbors": args.neighbors, "sparse_max": sparse_max},
        metrics=metrics,
        seed=args.seed,
        dataset_info={"splits_dir": args.splits_dir, "eval_on": args.eval_on, "num_users": num_users,
                      "num_items": num_items, "id_format": "namespaced" if namespaced else "plain",
                      "metadata_coverage": round(coverage, 4)},
        runtime_seconds=time.time() - t_start,
        notes="category_oracle results are an upper bound (query built from held-out items); do not report as a result.",
    )
    print(f"\nsaved -> {exp_dir}")


if __name__ == "__main__":
    main()
