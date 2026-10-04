"""
Run the package/tools on your REAL data (stage 3 outputs + raw item metadata).

Needs (paths come from configs/data_paths.yaml, default tag = run_tag.yaml):
  - resource/splits/<tag>/{train,validation}.parquet   (stage 3)
  - resource/mapped/<tag>/{user2id,item2id}.json       (stage 3)
  - resource/raw/meta_<Domain>.jsonl.gz per domain     (raw metadata; domains whose
    file is missing are skipped, and with none the corpus comes from stage 3 output only)

Run from the project root:

    PYTHONPATH=. python scripts/py/run_tools.py
    PYTHONPATH=. python scripts/py/run_tools.py --tag vg_toys --domain Video_Games

Only train is used to fit the model and validation is used to check it, so
nothing here touches the test split.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from package.config import get_data_paths, get_domains, load_config
from package.data.loader import load_item_metadata
from package.data.mapping import load_mappings
from package.tools.corpus import ItemCorpus
from package.tools.ranking.item_cf_tool import ItemCFTool
from package.tools.ranking.reco_model_tool import RecoModelTool
from package.tools.recommenders.baselines import ItemKNNRecommender, PopularityRecommender
from package.tools.score import BaselineScorer
from package.tools.sql_query.query_tool import QueryTool
from package.tools.sql_query.sql_tool import SQLTool

LOG_PATH = ROOT / "experiments" / "run_tools.log"  # fixed location, overwritten each run


class _Tee:
    """Send everything printed to the terminal to the log file as well."""

    def __init__(self, *streams) -> None:
        self.streams = streams

    def write(self, text: str) -> int:
        for st in self.streams:
            st.write(text)
        return len(text)

    def flush(self) -> None:
        for st in self.streams:
            st.flush()


failures: list[str] = []


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[ OK ] {name}" if ok else f"[FAIL] {name}", f"-- {detail}" if detail else "")
    if not ok:
        failures.append(name)


def show_result(name: str, result, preview_key: str, n: int = 3) -> None:
    if not result.ok:
        check(name, False, f"tool error: {result.error}")
        return
    rows = result.data.get(preview_key, [])
    check(name, True, f"{len(rows)} row(s) in '{preview_key}'")
    for r in rows[:n]:
        print("        ", {k: r[k] for k in list(r)[:6]})


def load_meta(meta_args: list[tuple[str, str]], wanted: dict[str, set[str]]) -> pd.DataFrame:
    """Stream each metadata file, keeping only items that appear in the splits."""
    return load_item_metadata(meta_args, keep=lambda domain, asin: asin in wanted.get(domain, ()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", help="Tên lần chạy (mặc định: tag trong run_tag.yaml).")
    ap.add_argument("--domain", action="append",
                    help="Domain có meta để nạp (lặp lại; mặc định: tất cả trong domains.yaml).")
    ap.add_argument("--model", choices=["knn", "popularity"], default="knn",
                    help="knn needs a lot of RAM on big data; popularity is a light fallback")
    ap.add_argument("--neighbors", type=int, help="mặc định: baselines.item_knn.k trong baselines.yaml")
    ap.add_argument("--eval-users", type=int, default=200)
    ap.add_argument("--negatives", type=int, default=99)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    args.neighbors = args.neighbors or load_config("baselines")["baselines"]["item_knn"]["k"]
    data_paths = get_data_paths(args.tag)
    args.splits_dir, args.mapping_dir = str(data_paths.splits_dir), str(data_paths.mapped_dir)
    meta_args = []
    for domain in args.domain or get_domains():
        meta_path = data_paths.meta_path(domain)
        if meta_path.exists():
            meta_args.append((domain, str(meta_path)))
        else:
            print(f"  note: {meta_path} not found; skipping metadata for {domain}")
    has_meta = bool(meta_args)
    rng = random.Random(args.seed)

    # ------------------------------------------------------------------ data
    section("Load stage 3 outputs")
    splits = Path(args.splits_dir)
    cols = ["user_idx", "item_idx", "domain", "original_item_id", "parent_asin"]
    train = pd.read_parquet(splits / "train.parquet", columns=cols)
    val = pd.read_parquet(splits / "validation.parquet", columns=cols)
    user2id, item2id = load_mappings(args.mapping_dir)
    print(f"  train={len(train):,} validation={len(val):,} users={len(user2id):,} items={len(item2id):,}")
    check("item2id keys are namespaced 'Domain::asin'", all("::" in k for k in list(item2id)[:1000]))

    all_items = pd.concat([train, val])[["domain", "original_item_id", "parent_asin"]].drop_duplicates("parent_asin")
    wanted = {d: set(g["original_item_id"]) for d, g in all_items.groupby("domain")}

    # ---------------------------------------------------------------- corpus
    if has_meta:
        section("Build item corpus from raw metadata")
        missing_meta_domains = set(wanted) - {d for d, _ in meta_args}
        if missing_meta_domains:
            print(f"  note: no meta file for {sorted(missing_meta_domains)}; those items won't be in the corpus")
        meta = load_meta(meta_args, wanted)
        corpus = ItemCorpus.from_dataframe(meta)
        check("corpus built", len(meta) > 0, f"{len(meta):,} items, domains={corpus.domains()}")
        sample_ids = list(item2id)[:5000]
        found = len(corpus.item_domains(sample_ids))
        check("most split items have metadata", found / len(sample_ids) > 0.5,
              f"{found}/{len(sample_ids)} of the first 5000 mapped items are in the corpus")
    else:
        section("Build item corpus from stage 3 output only (no title/price/rating/store)")
        # stage 3 rows already carry namespaced parent_asin + original_item_id + domain,
        # which is exactly what ItemCorpus.from_dataframe accepts. Everything else is NULL.
        corpus = ItemCorpus.from_dataframe(all_items.reset_index(drop=True))
        check("corpus built", len(all_items) > 0, f"{len(all_items):,} items, domains={corpus.domains()}")
        print("  note: price/rating/store/category filters can't be tested in this mode")
    corpus_ids = list(corpus.item_domains(list(item2id)))  # mapped items that exist in the corpus

    # ------------------------------------------------------------ SQL tools
    section("QueryTool / SQLTool on the corpus")
    query, sql = QueryTool(corpus), SQLTool(corpus)
    top = sql(limit=5)
    show_result("SQLTool: top 5 by rating_number", top, "candidates")
    if has_meta:
        show_result("SQLTool: price<=30, rating>=4.5, 100+ ratings",
                    sql(filters={"price_max": 30, "min_rating": 4.5, "min_rating_number": 100}, limit=5), "candidates")
    for d in corpus.domains():
        r = sql(filters={"domain": d}, limit=3)
        show_result(f"SQLTool: domain={d}", r, "candidates")
    if top.ok and top.data["candidates"]:
        ids = [c["item_id"] for c in top.data["candidates"]]
        r = query(item_ids=ids)
        check("QueryTool: look up those ids", r.ok and not r.data["missing_item_ids"])
    r = query(query="SELECT domain, COUNT(*) AS n FROM items GROUP BY domain")
    show_result("QueryTool: items per domain", r, "items", n=5)
    check("QueryTool rejects DELETE", not query(query="DELETE FROM items").ok)

    # ----------------------------------------------------------------- model
    section(f"Fit {args.model} on TRAIN only")
    t0 = time.time()
    model = (ItemKNNRecommender(args.neighbors) if args.model == "knn" else PopularityRecommender()).fit(train)
    print(f"  fitted in {time.time() - t0:.0f}s")
    scorer = BaselineScorer(model)
    reco = RecoModelTool(scorer, user2id, item2id, corpus=corpus)

    # pick a real validation user who has train history
    train_users = set(train["user_idx"].unique())
    val_by_user = val.groupby("user_idx")["item_idx"].apply(set)
    eligible = [u for u in val_by_user.index if u in train_users]
    check("validation users with train history exist", len(eligible) > 0, f"{len(eligible):,} users")
    if not eligible:
        sys.exit(1)

    id2item = {v: k for k, v in item2id.items()}
    id2user = {v: k for k, v in user2id.items()}
    demo_user = id2user[eligible[0]]
    users = rng.sample(eligible, min(args.eval_users, len(eligible)))
    seen_by_user = train[train["user_idx"].isin(set(users) | {eligible[0]})].groupby("user_idx")["item_idx"].apply(set)
    hist = sorted(seen_by_user[eligible[0]])
    print(f"  demo user {demo_user} has {len(hist)} train interactions")

    # ---------------------------------------------------------------- ItemCF
    section("ItemCFTool / RecoModelTool on a real user")
    if args.model == "knn":
        cf = ItemCFTool(model, item2id, corpus=corpus)
        seeds = [id2item[i] for i in hist[:3]]
        r = cf(items=seeds, top_k=5)
        show_result("ItemCFTool: neighbours of the user's first 3 items", r, "candidates")
    else:
        print("  (skipped ItemCFTool: needs --model knn)")

    pool = sql(filters={"exclude_item_ids": [id2item[i] for i in hist]}, limit=200)
    r = reco(user_id=demo_user, candidates=pool.data["candidates"], top_k=5)
    show_result("RecoModelTool: rank SQLTool's top-200 for the user", r, "ranked")
    if r.ok:
        check("not treated as cold start", r.data["cold_start"] is False)
        check("no already-seen item in the ranking",
              not ({x["item_id"] for x in r.data["ranked"]} & {id2item[i] for i in hist}))

    # -------------------------------------------- does ranking beat random?
    section(f"Ranking sanity check ({args.eval_users} validation users, 1 held-out item vs {args.negatives} random negatives)")
    hits_model = hits_random = n = 0
    k = 10
    for u in users:
        held = [id2item[i] for i in val_by_user[u]]
        if not held:
            continue
        pos = rng.choice(held)
        seen = seen_by_user[u]
        negs = []
        while len(negs) < args.negatives:
            c = rng.choice(corpus_ids)
            if c != pos and item2id[c] not in seen and c not in negs:
                negs.append(c)
        cands = [pos] + negs
        res = reco(user_id=id2user[u], candidates=cands, exclude_seen=False)
        if not res.ok:
            continue
        ranked = [x["item_id"] for x in res.data["ranked"]]
        hits_model += pos in ranked[:k]
        hits_random += pos in rng.sample(cands, k)
        n += 1
    if n:
        print(f"  HR@{k} model={hits_model / n:.3f}  random={hits_random / n:.3f}  (n={n})")
        check("model beats random ranking", hits_model > hits_random,
              "if this fails on real data, look at candidate/ID alignment before blaming the model")
    else:
        check("ranking sanity check ran", False, "no usable users")

    # ---------------------------------------------------------------- result
    section("Summary")
    if failures:
        print("FAILED:", ", ".join(failures))
        sys.exit(1)
    print("All real-data checks passed.")


if __name__ == "__main__":
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as log_file:
        real_out, real_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _Tee(real_out, log_file), _Tee(real_err, log_file)
        try:
            print(f"log -> {LOG_PATH}")
            main()
        except Exception:
            traceback.print_exc()  # goes to the terminal AND the log
            sys.exit(1)
        finally:
            sys.stdout, sys.stderr = real_out, real_err