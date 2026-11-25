"""Phase 4a — extractor run variance: agreement across repeated extractions.

Compares extractor_outputs.jsonl (run A, temp 0) against
extractor_outputs_t0b.jsonl (run B, temp 0 — provider determinism) and
extractor_outputs_t07.jsonl (run C, temp 0.7 — sampling variance) on the same
152 original requests. Per-slot exact agreement + kind agreement + struct rate.

Usage: python investigations/spec_benchmark/variance.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OUT = Path("investigations/spec_benchmark")


def load(tag: str) -> dict[str, dict]:
    p = OUT / f"extractor_outputs{tag}.jsonl"
    return {r["request_id"]: r for r in
            (json.loads(l) for l in open(p, encoding="utf-8") if l.strip())
            if r["variant"] == "original"}


def slot(spec: dict | None, name: str):
    if not isinstance(spec, dict):
        return None
    s = spec.get(name)
    if isinstance(s, dict):
        return s.get("value")
    return s


def norm_excl(spec: dict | None) -> tuple[frozenset, frozenset]:
    ex = (spec or {}).get("exclusions") or {}
    return (frozenset(ex.get("item_ids") or []),
            frozenset(ex.get("category_labels") or []))


def agree(a: dict | None, b: dict | None) -> dict[str, float]:
    out = {}
    out["kind"] = float((a or {}).get("kind") == (b or {}).get("kind"))
    out["cat_leaf"] = float(slot(a, "category_leaf") == slot(b, "category_leaf"))
    out["cat_coarse"] = float(slot(a, "category_coarse") == slot(b, "category_coarse"))
    out["seed"] = float((a or {}).get("seed_item_id") == (b or {}).get("seed_item_id"))
    out["exclusions"] = float(norm_excl(a) == norm_excl(b))
    out["language"] = float((a or {}).get("language") == (b or {}).get("language"))
    out["full_spec"] = float(
        all(out[k] == 1.0 for k in ("kind", "cat_leaf", "cat_coarse", "seed",
                                    "exclusions", "language")))
    return out


def main() -> None:
    base = load("")
    for tag, label in (("_t0b", "temp0 rerun"), ("_t07", "temp0.7")):
        other = load(tag)
        keys = sorted(set(base) & set(other))
        agg = defaultdict(list)
        for rid in keys:
            m = agree((base[rid].get("spec")), (other[rid].get("spec")))
            for k, v in m.items():
                agg[k].append(v)
        print(f"=== run A (temp0) vs {label} — n={len(keys)}")
        for k in ("kind", "cat_leaf", "cat_coarse", "seed", "exclusions",
                  "language", "full_spec"):
            v = agg[k]
            print(f"  {k:<12} {sum(v)/len(v):.3f}")
        # per-kind kind-agreement
        gold_kind = {json.loads(l)["request_id"]: json.loads(l)["kind"]
                     for l in open(OUT / "gold_specs.jsonl", encoding="utf-8")}
        by = defaultdict(list)
        for rid in keys:
            by[gold_kind[rid]].append(
                (base[rid].get("spec") or {}).get("kind")
                == (other[rid].get("spec") or {}).get("kind"))
        print("  kind-agree by gold kind:",
              {k: round(sum(v)/len(v), 3) for k, v in sorted(by.items())})


if __name__ == "__main__":
    main()
