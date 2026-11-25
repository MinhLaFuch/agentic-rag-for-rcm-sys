"""Compare Amazon Reviews 2023 raw sources (UCSD vs HuggingFace) and optional local files.

Usage:
    python compare_amazon_sources.py --domain Subscription_Boxes --out out_dir
    python compare_amazon_sources.py --domain Subscription_Boxes --out out_dir \
        --local meta=path/to/meta.parquet --local reviews=path/to/reviews.parquet

Sources:
    ucsd : https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/...
           (the datarepo.eng.ucsd.edu links in the HF README currently 404)
    hf   : McAuley-Lab/Amazon-Reviews-2023  raw/meta_categories/meta_{D}.jsonl
           raw/review_categories/{D}.jsonl
    local: parquet / jsonl / jsonl.gz files supplied via --local kind=path

Outputs report.json in --out with per-source field stats and pairwise diffs.
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path

UCSD_BASE = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw"
HF_REPO = "McAuley-Lab/Amazon-Reviews-2023"
MAX_COUNTER = 300_000  # cap per-field value counters to bound memory


def canon(v):
    """Canonical string form of a value for hashing / multiset comparison."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    try:
        return json.dumps(v, sort_keys=True, ensure_ascii=False)
    except TypeError:
        return str(v)


def nonempty(v):
    if v is None:
        return False
    if isinstance(v, (str, list, tuple, dict, set)):
        return len(v) > 0
    return True


def iter_jsonl(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def iter_parquet(path):
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=50000):
        for row in batch.to_pylist():
            yield row


def iter_source(path):
    p = str(path).lower()
    if p.endswith(".parquet"):
        yield from iter_parquet(path)
    else:
        yield from iter_jsonl(path)


def download(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    print(f"  downloading {url} -> {dest}", flush=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    tmp.rename(dest)
    return dest


def hf_file(rel):
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(HF_REPO, rel, repo_type="dataset"))


def collect(path_or_iter, kind):
    """Stream rows; return stats dict."""
    n = 0
    fields = {}          # name -> {"nonempty": int, "types": Counter, "values": Counter|None}
    row_hashes = Counter()
    users = set()
    items = set()
    ts_min = ts_max = None
    asin_ne_parent = 0
    categories_empty = 0
    has_meta = 0
    date_first_available = 0
    details_keys = Counter()

    it = iter_source(path_or_iter) if not hasattr(path_or_iter, "__iter__") or isinstance(path_or_iter, (str, Path)) else path_or_iter
    for row in it:
        n += 1
        if n % 200000 == 0:
            print(f"    ... {n} rows", flush=True)
        h = hashlib.sha1(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
        row_hashes[h] += 1
        for k, v in row.items():
            st = fields.setdefault(k, {"nonempty": 0, "types": Counter(), "values": Counter()})
            st["types"][type(v).__name__] += 1
            if nonempty(v):
                st["nonempty"] += 1
                if len(st["values"]) < MAX_COUNTER:
                    st["values"][canon(v)] += 1
        # project-relevant metrics
        if kind == "reviews":
            u = row.get("user_id")
            a = row.get("asin")
            if u:
                users.add(u)
            if a:
                items.add(a)
            t = row.get("timestamp")
            if isinstance(t, (int, float)):
                ts_min = t if ts_min is None else min(ts_min, t)
                ts_max = t if ts_max is None else max(ts_max, t)
            if row.get("parent_asin") and row.get("asin") and row["asin"] != row["parent_asin"]:
                asin_ne_parent += 1
        else:
            cats = row.get("categories")
            if not cats:
                categories_empty += 1
            else:
                has_meta += 1
            d = row.get("details")
            if isinstance(d, dict):
                for dk in d:
                    details_keys[dk] += 1
                if nonempty(d.get("Date First Available")):
                    date_first_available += 1

    out = {
        "n_rows": n,
        "fields": {k: {"nonempty": v["nonempty"], "pct": round(100 * v["nonempty"] / max(n, 1), 2),
                       "types": dict(v["types"]),
                       "values": v["values"] if len(v["values"]) < MAX_COUNTER else None}
                  for k, v in fields.items()},
        "row_hashes": row_hashes,
    }
    if kind == "reviews":
        out["metrics"] = {
            "n_users": len(users), "n_items": len(items),
            "ts_min": ts_min, "ts_max": ts_max,
            "asin_ne_parent": asin_ne_parent,
            "asin_ne_parent_pct": round(100 * asin_ne_parent / max(n, 1), 3),
        }
    else:
        out["metrics"] = {
            "categories_empty": categories_empty,
            "categories_empty_pct": round(100 * categories_empty / max(n, 1), 2),
            "date_first_available": date_first_available,
            "date_first_available_pct": round(100 * date_first_available / max(n, 1), 2),
            "details_keys_top": details_keys.most_common(30),
        }
    return out


def diff_values(a_fields, b_fields, label_a, label_b):
    """Per-field multiset value diff between two collected stats."""
    diffs = {}
    all_keys = sorted(set(a_fields) | set(b_fields))
    for k in all_keys:
        fa = a_fields.get(k)
        fb = b_fields.get(k)
        if fa is None:
            diffs[k] = {"only_in": label_b, "nonempty_b": fb["nonempty"] if fb else 0}
            continue
        if fb is None:
            diffs[k] = {"only_in": label_a, "nonempty_a": fa["nonempty"]}
            continue
        va, vb = fa.get("values"), fb.get("values")
        if va is None or vb is None:
            diffs[k] = {"values_skipped": "counter cap reached"}
            continue
        only_a = va - vb
        only_b = vb - va
        if only_a or only_b:
            ex_a = [v[:120] for v, _ in only_a.most_common(2)]
            ex_b = [v[:120] for v, _ in only_b.most_common(2)]
            diffs[k] = {
                "n_only_" + label_a: int(sum(only_a.values())),
                "n_only_" + label_b: int(sum(only_b.values())),
                "examples_" + label_a: ex_a,
                "examples_" + label_b: ex_b,
            }
    return diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--local", action="append", default=[],
                    help="kind=path, kind in {meta, reviews}; repeatable")
    args = ap.parse_args()

    outdir = Path(args.out)
    cache = outdir / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    report = {"domain": args.domain, "sources": {}, "diffs": {}}

    # ---- resolve source paths ----
    srcs = {}
    for kind, rel in (("meta", f"meta_categories/meta_{args.domain}.jsonl"),
                      ("reviews", f"review_categories/{args.domain}.jsonl")):
        # UCSD raw (jsonl.gz)
        ucsd_rel = (f"meta_categories/meta_{args.domain}.jsonl.gz" if kind == "meta"
                    else f"review_categories/{args.domain}.jsonl.gz")
        ucsd_path = cache / f"ucsd_{kind}_{args.domain}.jsonl.gz"
        try:
            download(f"{UCSD_BASE}/{ucsd_rel}", ucsd_path)
            srcs[f"ucsd_{kind}"] = ucsd_path
        except Exception as e:
            print(f"  UCSD {kind} download failed: {e}", flush=True)
        # HF raw (jsonl)
        try:
            srcs[f"hf_{kind}"] = hf_file(f"raw/{rel}")
        except Exception as e:
            print(f"  HF {kind} fetch failed: {e}", flush=True)

    for idx, item in enumerate(args.local):
        kind, _, path = item.partition("=")
        kind = kind.strip()
        if kind in ("meta", "reviews") and path:
            name = f"local_{kind}"
            if name in srcs:
                name = f"local_{kind}_{idx}"
            srcs[name] = Path(path)

    # ---- collect stats ----
    for name, path in srcs.items():
        kind = "meta" if "meta" in name else "reviews"
        print(f"[collect] {name} <- {path}", flush=True)
        stats = collect(str(path), kind)
        stats["path"] = str(path)
        stats["row_hashes"] = dict(stats["row_hashes"])
        report["sources"][name] = stats
        print(f"  rows={stats['n_rows']} fields={len(stats['fields'])}", flush=True)

    # ---- pairwise diffs ----
    names = list(report["sources"])
    for kind in ("meta", "reviews"):
        ks = [n for n in names if ("meta" in n) == (kind == "meta")]
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                a, b = ks[i], ks[j]
                fa = report["sources"][a]["fields"]
                fb = report["sources"][b]["fields"]
                d = diff_values(fa, fb, a, b)
                # exact row-hash overlap
                ha = Counter(report["sources"][a]["row_hashes"])
                hb = Counter(report["sources"][b]["row_hashes"])
                common = sum((ha & hb).values())
                report["diffs"][f"{a}__vs__{b}"] = {
                    "field_value_diffs": d,
                    "identical_rows": common,
                    "n_a": report["sources"][a]["n_rows"],
                    "n_b": report["sources"][b]["n_rows"],
                }
                print(f"[diff] {a} vs {b}: identical_rows={common}/{report['sources'][a]['n_rows']}/{report['sources'][b]['n_rows']}, fields_with_value_diffs={sum(1 for v in d.values() if 'n_only_' in str(v) or v.get('only_in'))}", flush=True)

    # strip bulky value counters from report (keep diffs + stats)
    for s in report["sources"].values():
        for f in s["fields"].values():
            f.pop("values", None)

    out_path = outdir / "report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
