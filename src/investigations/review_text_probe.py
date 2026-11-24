"""Probe: does REVIEW text contain query signal for missed targets?

Final enrichment check — meta fields (features/description/details/brand)
already showed ~1-2% new lexical signal and negative semantic delta
(dropped_fields_probe, semantic_enrichment_probe). This covers the last
dropped channel: review `title` + `text` (stage-1 drops in clean_domain).

Same missed-target set as dropped_fields_probe (reads its JSON rows).
new_signal = query tokens found in the item's review text but absent from
title+categories. Read-only. Output: investigations/review_text_probe.json
"""
import gzip
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE.parent
RUN = SRC / "experiments" / "agent_eval" / "prompt_fix" / "exp_2" / "run_1"
CORPUS = SRC / "resource" / "corpus" / "multi_domain" / "corpus_multi_domain.sqlite"
RAW = SRC / "resource" / "raw"
OUT = HERE / "review_text_probe.json"
MAX_REVIEWS_PER_ITEM = 500  # cap token accumulation per item

sys.path.insert(0, str(HERE))
from dropped_fields_probe import tokens  # noqa: E402


def main() -> None:
    prev = json.loads((HERE / "dropped_fields_probe.json").read_text(encoding="utf-8"))
    misses = prev["rows"]  # request_id, kind, item_id
    requests = {}
    for line in open(RUN / "requests.jsonl", encoding="utf-8"):
        r = json.loads(line)
        requests[r["request_id"]] = r

    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    items = {r[0]: {"title": r[1] or "", "main_category": r[2] or ""}
             for r in conn.execute("SELECT item_id, title, main_category FROM items")}
    cats = defaultdict(list)
    for iid, cat in conn.execute("SELECT item_id, category FROM item_categories"):
        cats[iid].append(cat)
    conn.close()

    needed = defaultdict(set)
    for m in misses:
        dom, asin = m["item_id"].split("::", 1)
        needed[dom].add(asin)

    # review_tokens[item_id] = set of tokens across that item's reviews
    review_tokens = {}
    review_counts = defaultdict(int)
    for dom, asins in needed.items():
        path = RAW / f"{dom}.jsonl.gz"
        if not path.exists():
            print(f"{dom}: review file missing")
            continue
        found = 0
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                asin = row.get("parent_asin")
                if asin not in asins:
                    continue
                iid = f"{dom}::{asin}"
                if review_counts[iid] >= MAX_REVIEWS_PER_ITEM:
                    continue
                review_counts[iid] += 1
                found += 1
                toks = tokens((row.get("title") or "") + " " + (row.get("text") or ""))
                review_tokens.setdefault(iid, set()).update(toks)
        print(f"{dom}: {found} reviews scanned for {len(asins)} items", flush=True)

    rows = []
    for m in misses:
        rid, kind, tid = m["request_id"], m["kind"], m["item_id"]
        q = tokens(requests[rid]["text"])
        if not q:
            continue
        it = items.get(tid, {})
        visible = tokens((it.get("title") or "") + " " + (it.get("main_category") or "")
                         + " " + " ".join(cats.get(tid, [])))
        rtoks = review_tokens.get(tid, set())
        new_sig = q & rtoks - visible
        rows.append({
            "request_id": rid, "kind": kind, "item_id": tid,
            "n_query_tokens": len(q),
            "n_reviews": review_counts.get(tid, 0),
            "has_review_text": bool(rtoks),
            "new_signal_coverage": round(len(new_sig) / len(q), 3),
            "new_signal_tokens": sorted(new_sig)[:10],
        })

    def agg(sub):
        n = len(sub)
        return {
            "n": n,
            "pct_with_review_text": round(100 * sum(1 for r in sub if r["has_review_text"]) / n, 1),
            "pct_new_signal_ge_15pct": round(100 * sum(1 for r in sub if r["new_signal_coverage"] >= 0.15) / n, 1),
            "mean_new_signal_coverage": round(sum(r["new_signal_coverage"] for r in sub) / n, 3),
        }

    report = {
        "method": "missed targets from dropped_fields_probe.json; review title+text "
                  f"tokens (cap {MAX_REVIEWS_PER_ITEM}/item) vs query tokens; "
                  "new_signal = in reviews but absent from title+categories.",
        "n_missed_targets": len(rows),
        "by_kind": {k: agg([r for r in rows if r["kind"] == k])
                    for k in sorted({r["kind"] for r in rows})},
        "top": sorted(rows, key=lambda r: -r["new_signal_coverage"])[:15],
        "rows": rows,
    }
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=1, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
