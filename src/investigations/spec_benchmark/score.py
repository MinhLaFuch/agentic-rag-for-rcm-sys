"""Phase-3c scoring harness: join gold_specs + extractor_outputs -> scores.

Builds ``label_ancestors`` once (streaming item_categories, cached to
``label_ancestors.json``), validates predictions against the Spec model for
``struct_strict``, scores every extractor row with ``score_extraction``, and
writes ``extract_scores.jsonl`` + ``extract_summary.json`` (per-variant means).

Usage:
  python investigations/spec_benchmark/score.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from package.evaluation.spec import Spec, score_extraction  # noqa: E402
from package.evaluation.spec._extract_metrics import _present  # noqa: E402

OUT = Path("investigations/spec_benchmark")
CORPUS = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
ANC_CACHE = OUT / "label_ancestors.json"


def build_label_ancestors() -> dict[str, set[str]]:
    """label -> set of ancestor labels, reconstructed from item rowid sequences."""
    if ANC_CACHE.is_file():
        return {k: set(v) for k, v in json.loads(ANC_CACHE.read_text()).items()}
    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    anc: dict[str, set[str]] = defaultdict(set)
    cur = conn.execute(
        "SELECT item_id, category FROM item_categories ORDER BY item_id, rowid")
    item_id, seq = None, []
    n = 0

    def flush() -> None:
        for i, lab in enumerate(seq):
            if i:
                anc[lab].update(seq[:i])

    for iid, cat in cur:
        if iid != item_id:
            flush()
            item_id, seq, n = iid, [], n + 1
            if n % 500_000 == 0:
                print(f"  ancestors pass: {n} items", flush=True)
        seq.append(cat)
    flush()
    conn.close()
    ANC_CACHE.write_text(json.dumps({k: sorted(v) for k, v in anc.items()}))
    return {k: set(v) for k, v in anc.items()}


def _adapt_for_spec(pred: dict) -> dict:
    """Extractor emits flat category_leaf/category_coarse strings; Spec wants
    CategorySlot objects. Wrap them; drop unknown keys."""
    out = {}
    for k in ("kind", "price_max", "min_rating", "exclusions", "seed_item_id",
              "attributes", "language", "uncategorized_ok"):
        if k in pred:
            out[k] = pred[k]
    for k in ("category_leaf", "category_coarse"):
        v = pred.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = {"value": v}
        elif isinstance(v, dict):
            out[k] = v
    return out


def strict_valid(pred: dict | None) -> bool:
    if not isinstance(pred, dict):
        return False
    try:
        Spec(**_adapt_for_spec(pred))
        return True
    except Exception:  # noqa: BLE001 — any validation failure counts as invalid
        return False


def main() -> None:
    gold = {json.loads(l)["request_id"]: json.loads(l)
            for l in open(OUT / "gold_specs.jsonl", encoding="utf-8") if l.strip()}
    anc = build_label_ancestors()
    anc_frozen = {k: frozenset(v) for k, v in anc.items()}

    scores_path = OUT / "extract_scores.jsonl"
    done = set()
    if scores_path.is_file():
        done = {json.loads(l)["row_id"] for l in open(scores_path, encoding="utf-8") if l.strip()}

    outs = [json.loads(l) for l in open(OUT / "extractor_outputs.jsonl", encoding="utf-8") if l.strip()]
    leaks = {}
    lpath = OUT / "leakcheck.jsonl"
    if lpath.is_file():
        leaks = {json.loads(l)["row_id"]: bool(json.loads(l).get("leak"))
                 for l in open(lpath, encoding="utf-8") if l.strip()}
    buf = []
    for r in outs:
        if r["row_id"] in done:
            continue
        g = gold.get(r["request_id"])
        if g is None:
            continue
        meta = dict(g, variant=r["variant"])
        m = score_extraction(g["spec"], meta, r.get("spec"),
                             label_ancestors=anc_frozen,
                             strict_valid=strict_valid(r.get("spec")))
        buf.append({"row_id": r["row_id"], "request_id": r["request_id"],
                    "kind": r["kind"], "variant": r["variant"],
                    "leaked": leaks.get(r["row_id"], False), **m})
        if len(buf) >= 200:
            with open(scores_path, "a", encoding="utf-8") as f:
                for b in buf:
                    f.write(json.dumps(b, ensure_ascii=False) + "\n")
            buf.clear()
    if buf:
        with open(scores_path, "a", encoding="utf-8") as f:
            for b in buf:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")

    # summary: mean of each metric, grouped by variant and kind
    rows = [json.loads(l) for l in open(scores_path, encoding="utf-8") if l.strip()]
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["variant"], r["kind"])].append(r)
        groups[("ALL", r["variant"])].append(r)
        tag = f"{r['variant']}|{'leaked' if r.get('leaked') else 'clean'}"
        groups[(tag, "ALL")].append(r)
    summary = {}
    for (variant, kind), rs in sorted(groups.items()):
        keys = [k for k in rs[0] if k not in ("row_id", "request_id", "kind", "variant")]
        summary[f"{variant}|{kind}"] = {
            "n": len(rs),
            **{k: round(sum(x[k] for x in rs) / len(rs), 4) for k in keys},
        }
    (OUT / "extract_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"scored {len(rows)} rows -> {scores_path}; "
          f"{len(summary)} groups -> extract_summary.json", flush=True)


if __name__ == "__main__":
    main()
