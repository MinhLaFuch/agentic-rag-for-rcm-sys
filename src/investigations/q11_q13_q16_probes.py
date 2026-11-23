"""Q11 + Q13 + Q14 + Q15(corpus side) + Q16 — read-only data probes.

Single pass over: raw corpus sqlite (main.* tables), train/val/test parquets,
item2id mapping, campaign_005 requests.jsonl. Outputs
investigations/q11_q13_q16_probes.json
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
SPLITS = Path("resource/splits/multi_domain")
ITEM2ID = Path("resource/mapped/multi_domain/item2id.json")
REQS = Path("experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/requests.jsonl")
CUTOFF_1 = 1617737606134
CUTOFF_2 = 1651701127817
OUT = Path(__file__).parent / "q11_q13_q16_probes.json"

report: dict = {}

# ---------- load ----------
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
item2id = json.loads(ITEM2ID.read_text(encoding="utf-8"))
id2item = {v: k for k, v in item2id.items()}
requests = [json.loads(l) for l in open(REQS, encoding="utf-8")]
target_names = sorted({id2item[t] for r in requests for t in r.get("targets", []) if t in id2item})
print(f"targets={len(target_names)} requests={len(requests)}", flush=True)

train = pd.read_parquet(SPLITS / "train.parquet",
                        columns=["user_idx", "item_idx", "timestamp", "domain", "user_id"])
val = pd.read_parquet(SPLITS / "validation.parquet", columns=["item_idx"])
test = pd.read_parquet(SPLITS / "test.parquet", columns=["item_idx"])
print("splits loaded", flush=True)

# ================= Q11: cross-domain users =================
# user_id -> set of domains (train only); drop_duplicates+groupby is C-fast
# (the earlier apply(lambda)->set version was O(n) Python and never finished)
# bitmask trick: domain->power-of-2, sum over unique (user,domain) pairs = combo mask
BIT = {"Electronics": 1, "Toys_and_Games": 2, "Video_Games": 4}
ud = train[["user_id", "domain"]].drop_duplicates()
ud["bit"] = ud["domain"].astype(str).map(BIT).fillna(0).astype(np.int64)
bits = ud.groupby("user_id")["bit"].sum()
BIT2NAME = {v: k for k, v in BIT.items()}
def combo_name(mask: int) -> str:
    return "+".join(n for b, n in BIT2NAME.items() if mask & b)
vc = bits.value_counts()
multi_masks = vc[vc.index > 0]
# users with >1 domain = bitmask with >=2 bits set  (m & (m-1)) != 0
multi = bits[(bits & (bits - 1)) != 0]
n_users = len(bits)
report["Q11_cross_domain"] = {
    "method": "train.parquet drop_duplicates(user_id,domain) -> bitmask per user "
              "(Electronics=1,Toys=2,VG=4); user2id keys inspected for namespace prefix",
    "train_users": int(n_users),
    "multi_domain_users": int(len(multi)),
    "pct_multi_domain": round(100 * len(multi) / n_users, 3),
    "domain_combo_counts": {combo_name(int(m)): int(c) for m, c in multi_masks.items()
                            if bin(int(m)).count("1") > 1},
    "examples": [],
}
# merge evidence: pick 3 multi-domain users, show their cross-domain item counts
ex_users = multi.index[:3].tolist()
for u in ex_users:
    sub = train[train.user_id == u]
    by_dom = sub.groupby("domain").size().to_dict()
    report["Q11_cross_domain"]["examples"].append({
        "user_id": str(u)[:24], "interactions_by_domain": {k: int(v) for k, v in by_dom.items()},
        "distinct_items": int(sub.item_idx.nunique()), "total_rows": int(len(sub))})
# user2id key format check (namespaced or raw?)
sample_keys = list(item2id.keys())[:3]
user2id = json.loads((SPLITS.parent / "mapped" / "multi_domain" / "user2id.json").read_text(encoding="utf-8")) if (SPLITS.parent / "mapped" / "multi_domain" / "user2id.json").exists() else {}
ukeys = list(user2id.keys())[:3]
report["Q11_cross_domain"]["user2id_sample_keys"] = ukeys
report["Q11_cross_domain"]["user2id_has_domain_prefix"] = any("::" in k for k in list(user2id.keys())[:10000])
report["Q11_cross_domain"]["note"] = ("tag_domain.py docstring: user_id intentionally NOT namespaced — "
    "same raw Amazon reviewer ID across domains is treated as one user (deliberate). "
    "Collision risk: Amazon reviewer IDs are account-level so same ID = same person is plausible; "
    "no positive evidence of collision found, but cannot be proven from data alone.")
del ud, bits, multi, train  # Q16 reloads train later anyway
print("Q11 done", flush=True)

# ================= Q13: first_seen_ts =================
fs = pd.DataFrame(conn.execute(
    "SELECT domain, first_seen_ts FROM items WHERE first_seen_ts IS NOT NULL").fetchall(),
    columns=["domain", "first_seen_ts"])
fs["bucket"] = pd.cut(fs.first_seen_ts,
    [0, CUTOFF_1, CUTOFF_2, 2**62],
    labels=["<=cutoff_1", "(c1,c2]", ">cutoff_2"], right=True)
q13 = {
    "method": "min(timestamp) per namespaced item over cleaned parquet (build_first_seen_timestamps.py); "
              "cleaning = drop missing required fields + dedup (user,parent_asin,timestamp) keep-last "
              "(+ optional validate_values rating[1,5], ts in [1995,2024)); NO verified-purchase filter",
    "n_items_with_first_seen": int(len(fs)),
    "distribution": fs["bucket"].value_counts().to_dict(),
    "pct_after_cutoff_1": round(100 * (fs.first_seen_ts > CUTOFF_1).mean(), 3),
    "pct_after_cutoff_2": round(100 * (fs.first_seen_ts > CUTOFF_2).mean(), 3),
    "by_domain": {},
}
for dom, g in fs.groupby("domain"):
    q13["by_domain"][dom] = {
        "n": int(len(g)),
        "pct_after_c1": round(100 * (g.first_seen_ts > CUTOFF_1).mean(), 3),
        "pct_after_c2": round(100 * (g.first_seen_ts > CUTOFF_2).mean(), 3)}
# hidden targets per domain (first_seen > cutoff_1)
tsub = ",".join("?" for _ in target_names)
trows = conn.execute(
    f"SELECT item_id, domain, first_seen_ts FROM items WHERE item_id IN ({tsub})", target_names).fetchall()
hidden = [r for r in trows if r[2] is None or r[2] > CUTOFF_1]
q13["hidden_targets_at_cutoff_1"] = {
    "n_targets": len(trows), "n_hidden": len(hidden),
    "by_domain": dict(Counter(r[1] for r in hidden)),
    "examples": [{"item_id": r[0], "domain": r[1], "first_seen_ts": r[2]} for r in hidden[:5]],
}
report["Q13_first_seen"] = q13
print("Q13 done", flush=True)

# ================= Q14: ASIN uniqueness / dup titles =================
asin_dom = conn.execute(
    "SELECT original_item_id, COUNT(DISTINCT domain) nd, COUNT(*) c FROM items "
    "GROUP BY original_item_id HAVING nd > 1").fetchall()
asin_within = conn.execute(
    "SELECT domain, original_item_id, COUNT(*) c FROM items "
    "GROUP BY domain, original_item_id HAVING c > 1 LIMIT 5").fetchall()
total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
# normalized-title duplicates across domains
title_rows = conn.execute("SELECT item_id, domain, title FROM items").fetchall()
norm_groups = defaultdict(set)
for iid, dom, title in title_rows:
    norm = re.sub(r"[^a-z0-9]+", "", (title or "").lower())[:120]
    if len(norm) >= 10:
        norm_groups[norm].add(iid)
dup_titles = {k: v for k, v in norm_groups.items() if len(v) > 1}
cross_dom_dup = sum(1 for v in dup_titles.values() if len({i.split("::")[0] for i in v}) > 1)
report["Q14_asin_titles"] = {
    "method": "original_item_id = raw parent_asin; group by ASIN across domains; "
              "normalized title = lowercase alnum-only prefix(120) hashed by exact match",
    "total_catalog_items": int(total_items),
    "asins_in_multiple_domains": int(len(asin_dom)),
    "pct_asins_multi_domain": round(100 * len(asin_dom) / total_items, 3),
    "items_in_multi_domain_asins": int(sum(r[2] for r in asin_dom)),
    "within_domain_asin_duplicates": [list(r) for r in asin_within],
    "exact_norm_title_dup_groups": int(len(dup_titles)),
    "dup_groups_spanning_domains": int(cross_dom_dup),
    "title_dup_examples": [
        {"norm": k, "items": sorted(v)[:4]} for k, v in list(dup_titles.items())[:5]],
}
del title_rows, norm_groups
print("Q14 done", flush=True)

# ================= Q15 corpus-side + Q16 =================
cat_items = {r[0] for r in conn.execute("SELECT DISTINCT item_id FROM item_categories")}
items_rows = conn.execute(
    "SELECT item_id, domain, rating_number, main_category, title FROM items").fetchall()
q15 = {"by_domain": {}, "method": "corpus items LEFT JOIN item_categories presence; main_category non-empty"}
q16_rows = []
miss_cat_by_rn = defaultdict(lambda: [0, 0])
for iid, dom, rn, mc, title in items_rows:
    has_cat = iid in cat_items
    has_mc = bool(mc and str(mc).strip())
    d = q15["by_domain"].setdefault(dom, {"n": 0, "with_item_categories": 0, "with_main_category": 0})
    d["n"] += 1
    d["with_item_categories"] += int(has_cat)
    d["with_main_category"] += int(has_mc)
    rn_f = float(rn) if rn is not None else np.nan
    if np.isnan(rn_f):
        b = "null"
    elif rn_f < 5: b = "<5"
    elif rn_f < 50: b = "5-49"
    elif rn_f < 500: b = "50-499"
    else: b = ">=500"
    miss_cat_by_rn[b][0] += int(not has_cat)
    miss_cat_by_rn[b][1] += 1
    q16_rows.append((iid, float(rn) if rn is not None else np.nan))
for dom, d in q15["by_domain"].items():
    d["pct_with_item_categories"] = round(100 * d["with_item_categories"] / d["n"], 3)
    d["pct_with_main_category"] = round(100 * d["with_main_category"] / d["n"], 3)
q15["missing_cat_rate_by_rating_number_bucket"] = {
    k: {"n": v[1], "missing_cat": v[0], "missing_cat_pct": round(100 * v[0] / v[1], 2)}
    for k, v in sorted(miss_cat_by_rn.items())}
report["Q15_categories"] = q15

rn_arr = np.array([r[1] for r in q16_rows])
valid = ~np.isnan(rn_arr)
report["Q16_rating_number"] = {
    "method": "rating_number = raw meta 'rating_number' string coerced numeric "
              "(Amazon global rating count); distribution over 2.64M catalog items",
    "n_items": int(len(rn_arr)), "n_null": int((~valid).sum()),
    "median": float(np.nanmedian(rn_arr)), "p90": float(np.nanpercentile(rn_arr, 90)),
    "max": float(np.nanmax(rn_arr)),
    "pct_lt5": round(100 * np.nanmean(rn_arr < 5), 3),
    "pct_null": round(100 * (~valid).mean(), 3),
}
# Spearman: rating_number vs train interaction count per item
train = pd.read_parquet(SPLITS / "train.parquet", columns=["item_idx"])
item_counts = train["item_idx"].value_counts()
train_u = pd.read_parquet(SPLITS / "validation.parquet", columns=["item_idx"])
test_u = pd.read_parquet(SPLITS / "test.parquet", columns=["item_idx"])
held_counts = pd.concat([val["item_idx"], test["item_idx"]]).value_counts()
rn_map = {i: r for i, r in q16_rows}  # item_id -> rn ; need item_idx->item_id
rn_by_idx = {}
for i, nm in id2item.items():
    if i in rn_map:
        rn_by_idx[i] = rn_map[nm]
common_tr = item_counts.index.intersection(pd.Index(list(rn_by_idx.keys())))
x_tr = np.array([rn_by_idx[i] for i in common_tr], dtype=float)
y_tr = item_counts.loc[common_tr].to_numpy(dtype=float)
m = ~(np.isnan(x_tr))
spearman_train = float(pd.Series(x_tr[m]).corr(pd.Series(y_tr[m]), method="spearman"))
common_he = held_counts.index.intersection(pd.Index(list(rn_by_idx.keys())))
x_he = np.array([rn_by_idx[i] for i in common_he], dtype=float)
y_he = held_counts.loc[common_he].to_numpy(dtype=float)
m2 = ~(np.isnan(x_he))
spearman_held = float(pd.Series(x_he[m2]).corr(pd.Series(y_he[m2]), method="spearman"))
report["Q16_rating_number"]["spearman_vs_train_interaction_count"] = spearman_train
report["Q16_rating_number"]["spearman_vs_heldout_interaction_count"] = spearman_held
report["Q16_rating_number"]["n_common_train"] = int(len(common_tr))
report["Q16_rating_number"]["n_common_heldout"] = int(len(common_he))
print("Q15/Q16 done", flush=True)

OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("wrote", OUT)
