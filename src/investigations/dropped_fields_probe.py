"""Probe: do dropped item-side fields contain query signal the pipeline can't see?

For requests where the baseline arm (prompt_fix exp_2) missed its targets,
measure whether the target's DROPPED meta fields (features, description,
details values, brand) contain request-query tokens that are absent from
the fields retrieval currently indexes (title + categories).

If missed targets have substantial "new signal" in dropped text, enriching
the item document (FTS/dense) has headroom. If not, enrichment won't help
this eval.

Read-only. Output: investigations/dropped_fields_probe.json
"""
import gzip
import json
import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE.parent
RUN = SRC / "experiments" / "agent_eval" / "prompt_fix" / "exp_2" / "run_1"
CORPUS = SRC / "resource" / "corpus" / "multi_domain" / "corpus_multi_domain.sqlite"
RAW = SRC / "resource" / "raw"
ITEM2ID = SRC / "resource" / "mapped" / "multi_domain" / "item2id.json"
OUT = HERE / "dropped_fields_probe.json"

TOKEN_RE = re.compile(r"[a-zA-ZÀ-ỹĐđ0-9]+")
# small stopword list: EN + common VI function words
STOP = set("""
a an the and or of for to in on at with by from is are was were be been being
this that these those it its as not no do does did have has had will would can
could should may might phải cần muốn tìm gợi ý cho tôi là có các một những và
của trong với được tôi bạn anh chị em nó họ này đó kia rất quá lắm mấy từng
sản phẩm sản-phẩm item items mua vừa mới rất giống tương tự similar recommend
gợi ý giới thiệu tư vấn shop cửa hàng giá rẻ tốt đẹp chính hãng new best top
""".split())


def tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "")
            if len(t) >= 3 and t.lower() not in STOP}


def meta_text(row: dict) -> str:
    """Concatenate the fields the pipeline drops at corpus build."""
    parts = []
    feats = row.get("features")
    if isinstance(feats, str):
        try:
            feats = json.loads(feats)
        except Exception:
            feats = [feats]
    if isinstance(feats, list):
        parts.extend(str(f) for f in feats)
    desc = row.get("description")
    if isinstance(desc, str):
        try:
            desc = json.loads(desc)
        except Exception:
            pass
    if isinstance(desc, list):
        parts.extend(str(d) for d in desc)
    elif desc:
        parts.append(str(desc))
    det = row.get("details")
    if isinstance(det, str):
        try:
            det = json.loads(det)
        except Exception:
            det = {}
    if isinstance(det, dict):
        parts.extend(str(v) for v in det.values())
    elif isinstance(det, list):
        parts.extend(str(v) for _, v in det)
    if row.get("brand"):
        parts.append(str(row["brand"]))
    return " ".join(parts)


def load_eval():
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
    return requests, recommended, scored


def main() -> None:
    requests, recommended, scored = load_eval()
    idx2id = {v: k for k, v in json.load(open(ITEM2ID)).items()}

    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    items = {r[0]: {"title": r[1] or "", "main_category": r[2] or ""}
             for r in conn.execute("SELECT item_id, title, main_category FROM items")}
    cats = {}
    for iid, cat in conn.execute("SELECT item_id, category FROM item_categories"):
        cats.setdefault(iid, []).append(cat)
    conn.close()

    # Collect missed targets: request scored task_success False or recall@10 == 0
    misses = []  # (request_id, kind, target_item_id)
    seen_targets = set()
    needed_asins = {}  # domain -> set(asin)
    for rid, req in requests.items():
        s = scored.get(rid, {})
        failed = (not s.get("task_success")) or (s.get("recall@10") or 0) == 0
        if not failed:
            continue
        rec = set(recommended.get(rid, []))
        for tidx in req.get("targets") or []:
            tid = idx2id.get(int(tidx))
            if tid is None:
                continue
            if tid in rec:
                continue  # target was recommended — not a retrieval miss
            misses.append((rid, req.get("kind"), tid))
            if tid not in seen_targets:
                seen_targets.add(tid)
                dom, asin = tid.split("::", 1)
                needed_asins.setdefault(dom, set()).add(asin)

    # Single pass per domain over raw meta, keep only needed ASINs
    meta = {}
    for dom, asins in needed_asins.items():
        path = RAW / f"meta_{dom}.jsonl.gz"
        if not path.exists():
            continue
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                asin = row.get("parent_asin")
                if asin in asins:
                    meta[f"{dom}::{asin}"] = row
        print(f"{dom}: needed={len(asins)} found={sum(1 for k in meta if k.startswith(dom + '::'))}")

    # Score each missed target
    per_request = {}
    rows = []
    for rid, kind, tid in misses:
        req = requests[rid]
        q = tokens(req.get("text", ""))
        if not q:
            continue
        it = items.get(tid, {})
        visible = tokens((it.get("title") or "") + " " + (it.get("main_category") or "")
                         + " " + " ".join(cats.get(tid, [])))
        row = meta.get(tid)
        has_dropped = row is not None and bool(meta_text(row))
        drop_toks = tokens(meta_text(row)) if row else set()
        new_sig = q & drop_toks - visible
        rec = {
            "request_id": rid, "kind": kind, "item_id": tid,
            "n_query_tokens": len(q),
            "query_visible_coverage": round(len(q & visible) / len(q), 3),
            "has_dropped_fields": has_dropped,
            "dropped_new_tokens": sorted(new_sig),
            "new_signal_coverage": round(len(new_sig) / len(q), 3),
            "title": (it.get("title") or "")[:100],
        }
        rows.append(rec)
        per_request.setdefault(rid, []).append(rec)

    # Aggregate
    def agg(sub):
        n = len(sub)
        if not n:
            return {}
        with_fields = [r for r in sub if r["has_dropped_fields"]]
        sig = [r for r in sub if r["new_signal_coverage"] >= 0.15]
        return {
            "n_missed_targets": n,
            "pct_with_dropped_fields": round(100 * len(with_fields) / n, 1),
            "pct_new_signal_ge_15pct": round(100 * len(sig) / n, 1),
            "mean_new_signal_coverage": round(sum(r["new_signal_coverage"] for r in sub) / n, 3),
            "mean_query_visible_coverage": round(sum(r["query_visible_coverage"] for r in sub) / n, 3),
        }

    by_kind = {}
    for kind in sorted({r["kind"] for r in rows}):
        by_kind[kind] = agg([r for r in rows if r["kind"] == kind])

    # Requests where >=1 missed target has new signal
    req_with_signal = sum(
        1 for rid, rs in per_request.items()
        if any(r["new_signal_coverage"] >= 0.15 for r in rs))

    report = {
        "method": "missed targets = gold targets not in recommended[:10] for "
                  "requests with task_success=False or recall@10=0 (prompt_fix exp_2). "
                  "new_signal = query tokens found in dropped meta fields "
                  "(features/description/details/brand) but absent from "
                  "title+categories. Review text NOT included (separate pass).",
        "n_requests_failed": len(per_request),
        "n_missed_targets": len(rows),
        "requests_with_any_new_signal": req_with_signal,
        "by_kind": by_kind,
        "examples": [r for r in rows if r["new_signal_coverage"] >= 0.3][:15],
        "rows": rows,
    }
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=1, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
