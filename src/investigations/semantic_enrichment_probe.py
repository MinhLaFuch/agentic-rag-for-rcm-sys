"""Probe: would features/description enrichment help DENSE retrieval?

The lexical probe (dropped_fields_probe) only rules out the FTS channel.
Dense retrieval is semantic — no token overlap needed. This probe embeds
(query, title_doc) vs (query, title_doc + features + description) for the
same missed targets, using the production model/doc format
(all-MiniLM-L6-v2, "title. Store: X. Main: Y. Categories: ...").

Headroom criterion per request: a missed target's ENRICHED similarity
exceeds the similarity of the WORST recommended item — i.e. enrichment
could plausibly move it into the top-10 if docs carried the extra text.

Read-only (meta scan + local embeddings). Output:
investigations/semantic_enrichment_probe.json
"""
import gzip
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
SRC = HERE.parent
RUN = SRC / "experiments" / "agent_eval" / "prompt_fix" / "exp_2" / "run_1"
CORPUS = SRC / "resource" / "corpus" / "multi_domain" / "corpus_multi_domain.sqlite"
RAW = SRC / "resource" / "raw"
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
OUT = HERE / "semantic_enrichment_probe.json"

sys.path.insert(0, str(HERE))
from dropped_fields_probe import meta_text  # noqa: E402


def doc_title(it: dict, cats: list[str]) -> str:
    return (f"{it.get('title') or ''}. Store: {it.get('store') or ''}. "
            f"Main: {it.get('main_category') or ''}. "
            f"Categories: {', '.join(sorted(cats))}.")


def load_missed():
    """Missed (request_id, kind, item_id) triples — same rule as lexical probe."""
    requests = {}
    for line in open(RUN / "requests.jsonl", encoding="utf-8"):
        r = json.loads(line)
        requests[r["request_id"]] = r
    recommended = {}
    for line in open(RUN / "trajectories.jsonl", encoding="utf-8"):
        t = json.loads(line)
        recommended[t["request_id"]] = t.get("recommended") or []
    scored = {}
    for line in open(RUN / "scored.jsonl", encoding="utf-8"):
        s = json.loads(line)
        scored[s["request_id"]] = s
    idx2id = {v: k for k, v in json.load(open(SRC / "resource/mapped/multi_domain/item2id.json")).items()}

    misses = []
    for rid, req in requests.items():
        s = scored.get(rid, {})
        if s.get("task_success") and (s.get("recall@10") or 0) > 0:
            continue
        rec = set(recommended.get(rid, []))
        for tidx in req.get("targets") or []:
            tid = idx2id.get(int(tidx))
            if tid and tid not in rec:
                misses.append((rid, req.get("kind"), tid))
    return requests, recommended, misses


def scan_meta(needed: dict[str, set[str]]) -> dict[str, str]:
    meta_texts = {}
    for dom, asins in needed.items():
        path = RAW / f"meta_{dom}.jsonl.gz"
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                asin = row.get("parent_asin")
                if asin in asins:
                    meta_texts[f"{dom}::{asin}"] = meta_text(row)
        print(f"{dom}: found {sum(1 for k in meta_texts if k.startswith(dom + '::'))}/{len(asins)}", flush=True)
    return meta_texts


def main() -> None:
    requests, recommended, misses = load_missed()
    print(f"missed targets: {len(misses)} across {len({m[0] for m in misses})} requests")

    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    items = {r[0]: dict(zip(("item_id", "domain", "original_item_id", "first_seen_ts",
                             "title", "store", "price", "average_rating",
                             "rating_number", "main_category"), r))
             for r in conn.execute("SELECT * FROM items")}
    cats = {}
    for iid, cat in conn.execute("SELECT item_id, category FROM item_categories"):
        cats.setdefault(iid, []).append(cat)
    conn.close()

    needed = {}
    for _, _, tid in misses:
        dom, asin = tid.split("::", 1)
        needed.setdefault(dom, set()).add(asin)
    # also need meta for recommended items? No — comparison uses their TITLE docs.
    meta_texts = scan_meta(needed)

    # Build text sets
    q_texts = {rid: req["text"] for rid, req in requests.items()}
    rec_ids = sorted({iid for rid in {m[0] for m in misses} for iid in recommended.get(rid, [])})
    tgt_ids = sorted({tid for _, _, tid in misses})

    texts, keys = [], []
    for rid in {m[0] for m in misses}:
        texts.append(q_texts[rid]); keys.append(("q", rid))
    for tid in rec_ids:
        it = items.get(tid)
        if it:
            texts.append(doc_title(it, cats.get(tid, []))); keys.append(("rec", tid))
    for tid in tgt_ids:
        it = items.get(tid)
        if not it:
            continue
        base = doc_title(it, cats.get(tid, []))
        texts.append(base); keys.append(("t", tid, "title"))
        enr = base + " " + (meta_texts.get(tid) or "")
        texts.append(enr[:4000]); keys.append(("t", tid, "enriched"))

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_ID)
    emb = model.encode(texts, batch_size=64, normalize_embeddings=True,
                       show_progress_bar=False)
    vec = {k: emb[i] for i, k in enumerate(keys)}

    # Per-request analysis
    per_req = []
    for rid, kind, tid in misses:
        pass
    by_req = {}
    for rid, kind, tid in misses:
        by_req.setdefault(rid, {"kind": kind, "targets": []})
        qv = vec.get(("q", rid))
        tv_t = vec.get(("t", tid, "title"))
        tv_e = vec.get(("t", tid, "enriched"))
        if qv is None or tv_t is None:
            continue
        rec_sims = [float(qv @ vec[("rec", iid)]) for iid in recommended.get(rid, [])
                    if ("rec", iid) in vec]
        by_req[rid]["targets"].append({
            "item_id": tid,
            "sim_title": round(float(qv @ tv_t), 4),
            "sim_enriched": round(float(qv @ tv_e), 4) if tv_e is not None else None,
            "has_meta": tid in meta_texts,
            "worst_rec_sim": round(min(rec_sims), 4) if rec_sims else None,
            "median_rec_sim": round(float(np.median(rec_sims)), 4) if rec_sims else None,
            "best_rec_sim": round(max(rec_sims), 4) if rec_sims else None,
        })

    # Aggregate
    rows = []
    for rid, d in by_req.items():
        for t in d["targets"]:
            if t["sim_enriched"] is None:
                continue
            t2 = dict(t); t2["request_id"] = rid; t2["kind"] = d["kind"]
            t2["delta"] = round(t["sim_enriched"] - t["sim_title"], 4)
            t2["beats_worst_rec"] = (t["worst_rec_sim"] is not None
                                     and t["sim_enriched"] > t["worst_rec_sim"])
            t2["beats_median_rec"] = (t["median_rec_sim"] is not None
                                      and t["sim_enriched"] > t["median_rec_sim"])
            rows.append(t2)

    def agg(sub):
        n = len(sub)
        return {
            "n": n,
            "mean_delta": round(sum(r["delta"] for r in sub) / n, 4),
            "pct_delta_pos": round(100 * sum(1 for r in sub if r["delta"] > 0) / n, 1),
            "pct_beats_worst_rec": round(100 * sum(1 for r in sub if r["beats_worst_rec"]) / n, 1),
            "pct_beats_median_rec": round(100 * sum(1 for r in sub if r["beats_median_rec"]) / n, 1),
            "mean_sim_title": round(sum(r["sim_title"] for r in sub) / n, 4),
            "mean_sim_enriched": round(sum(r["sim_enriched"] for r in sub) / n, 4),
        }

    by_kind = {k: agg([r for r in rows if r["kind"] == k])
               for k in sorted({r["kind"] for r in rows})}
    req_headroom = sum(
        1 for rid, d in by_req.items()
        if any(t.get("sim_enriched") is not None and t["worst_rec_sim"] is not None
               and t["sim_enriched"] > t["worst_rec_sim"]
               for t in d["targets"]))

    report = {
        "method": "cosine sim(query, title_doc) vs (query, title_doc+features+"
                  "description+details+brand); model all-MiniLM-L6-v2; doc format "
                  "matches multi_domain_semantic build. Headroom = enriched sim "
                  "beats worst recommended item's title-doc sim.",
        "n_missed_targets": len(rows),
        "n_requests": len(by_req),
        "requests_with_headroom": req_headroom,
        "by_kind": by_kind,
        "top_deltas": sorted(rows, key=lambda r: -r["delta"])[:15],
        "rows": rows,
    }
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=1, ensure_ascii=False)[:5000])


if __name__ == "__main__":
    main()
