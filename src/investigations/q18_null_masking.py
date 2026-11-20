"""Q18: does historical_static_catalog NULL-masking break FilterTool?

Read-only. Loads the real corpus, applies each metadata policy, and tests:
  1. Are price/average_rating/rating_number actually NULL for all visible items?
  2. Does empty-filter FilterTool still return popularity-ordered items?
     (compares top-10 vs ground-truth ORDER BY rating_number on main.items)
  3. Do price/rating filters return 0 matches under masking?
  4. Same checks under `snapshot` (no masking) as control.

Outputs: investigations/q18_null_masking.json + console summary.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.corpus import load_corpus
from package.corpus.apply_metadata_policy import apply_metadata_policy
from package.data.pipeline import build_meta_files
from package.tools import FilterTool

OUT = Path(__file__).parent / "q18_null_masking.json"
AS_OF = 1617737606549
RAW_DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"


def main() -> None:
    paths = resolve_bundle_paths()
    item2id = json.loads((paths.mapped_dir / "item2id.json").read_text(encoding="utf-8"))
    meta = build_meta_files(paths)

    raw = sqlite3.connect(RAW_DB)
    truth_top10 = [r[0] for r in raw.execute(
        "SELECT item_id FROM items ORDER BY rating_number IS NULL, rating_number DESC, item_id LIMIT 10")]
    raw.close()

    report = {"as_of": AS_OF, "truth_top10_by_rating_number": truth_top10, "policies": {}}

    for policy in ("historical_static_catalog", "snapshot"):
        corpus, _ = load_corpus(paths.corpus_path, meta, item2id, 0.5,
                                allow_missing_sources=True)
        apply_metadata_policy(corpus, policy, as_of_timestamp=AS_OF)
        conn = corpus._conn
        n_all = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        nulls = {c: conn.execute(f"SELECT COUNT(*) FROM items WHERE {c} IS NULL").fetchone()[0]
                 for c in ("price", "average_rating", "rating_number")}

        tool = FilterTool(corpus)
        t0 = time.time()
        empty = tool.execute(filters={}, limit=10)
        empty_ids = [c["item_id"] for c in empty["candidates"]]
        overlap = len(set(empty_ids) & set(truth_top10))

        filter_tests = {}
        for name, f in {
            "price_max_30": {"price_max": 30.0},
            "min_rating_4": {"min_rating": 4.0},
            "min_rating_number_1000": {"min_rating_number": 1000},
            "price_range": {"price_min": 10, "price_max": 50},
        }.items():
            try:
                o = tool.execute(filters=f, limit=5)
                filter_tests[name] = {"total_matches": o["total_matches"],
                                      "n_rows": len(o["candidates"]),
                                      "sample": [c["item_id"] for c in o["candidates"][:3]]}
            except Exception as exc:
                filter_tests[name] = {"error": f"{type(exc).__name__}: {exc}"}

        report["policies"][policy] = {
            "n_visible_items": n_all,
            "null_counts": nulls,
            "empty_filter": {
                "elapsed_s": round(time.time() - t0, 2),
                "top10": empty_ids,
                "overlap_with_true_popularity_top10": overlap,
                "total_matches": empty["total_matches"],
            },
            "filter_tests": filter_tests,
        }
        print(f"[{policy}] nulls={nulls} overlap={overlap}/10 "
              f"price_max_30={filter_tests['price_max_30'].get('total_matches')}", flush=True)
        del corpus

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
