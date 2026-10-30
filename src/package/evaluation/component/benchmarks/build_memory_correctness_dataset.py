"""Generate memory_correctness_dataset.jsonl from the independent oracle.

    python -m package.evaluation.component.benchmarks.build_memory_correctness_dataset          # (re)write
    python -m package.evaluation.component.benchmarks.build_memory_correctness_dataset --check  # fail on drift
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .memory_correctness_setup import create_test_interactions, create_test_mappings, create_test_meta, get_interactions_without_rating
from .memory_oracle import compute_memory_oracle, leakage_probe

DATASET_PATH = Path(__file__).with_name("memory_correctness_dataset.jsonl")

# (case_id, user_id, top_n, as_of, snapshot_mode, tags, description)
SPECS = [
    ("correctness_001", "nonexistent_user", 2, None, None, ["negative", "user_not_exists"], "User not in user2id"),
    ("correctness_002", "u_empty", 2, None, None, ["negative", "empty_history"], "User exists, zero interactions"),
    ("correctness_003", "u_short", 2, None, None, ["normal", "short_history"], "2 interactions"),
    ("correctness_004", "u_long", 3, None, None, ["normal", "long_history"], "10 interactions; recent_items capped"),
    ("correctness_005", "u_leakage_test", 3, -1, "pretruncated", ["cutoff", "before_all"], "cutoff before first event -> unknown"),
    ("correctness_006", "u_leakage_test", 3, 0, "pretruncated", ["cutoff", "at_first"], "cutoff == first timestamp (inclusive)"),
    ("correctness_007", "u_leakage_test", 3, 4, "pretruncated", ["cutoff", "mid"], "cutoff mid-history; ts 5,6 are future"),
    ("correctness_008", "u_leakage_test", 3, 6, "pretruncated", ["cutoff", "at_last"], "cutoff == last timestamp -> full profile"),
    ("correctness_009", "u_tie_categories", 2, None, None, ["edge_case", "tie_break"], "Puzzle/RPG tie at the top-n boundary -> alphabetical"),
    ("correctness_010", "u_null_prices", 2, None, None, ["edge_case", "null_prices"], "all prices NULL -> price_range None"),
    ("correctness_011", "u_equal_prices", 2, None, None, ["edge_case", "equal_prices"], "all items cost 1.0 -> min == max"),
    ("correctness_012", "u_outlier_price", 2, None, None, ["edge_case", "outlier_price"], "one 1000.0 item must define max"),
    ("correctness_013", "u_dup_items", 1, None, None, ["edge_case", "semantics_probe", "duplicate_items"],
     "vg_b bought twice. Oracle counts categories per DISTINCT item (tool SQL does); n_interactions counts rows"),
    ("correctness_014", "u_short", 10, None, None, ["edge_case", "top_n_exceeds_available"], "top_n larger than #categories"),
    ("correctness_015", "u_leakage_test", 3, 4, "untruncated", ["leakage_guard", "negative"],
     "full frame + as_of=4: the tool's leakage guard must raise LeakageError"),
    ("correctness_016", "u_leakage_test", 3, 9, "untruncated", ["leakage_guard", "control"],
     "full frame + as_of=9 (= max ts of ALL users, so no future rows anywhere): guard must NOT raise"),
    # Love/hate test cases
    ("correctness_017", "u_love_hate_mix", 5, None, None, ["love_hate", "mixed_ratings"],
     "User with ratings 5,4,3,2,1: love >=4, hate <=2"),
    ("correctness_018", "u_all_love", 5, None, None, ["love_hate", "all_love"],
     "All ratings >=4: love populated, hate empty"),
    ("correctness_019", "u_all_hate", 5, None, None, ["love_hate", "all_hate"],
     "All ratings <=2: hate populated, love empty"),
    ("correctness_020", "u_no_rating", 5, None, None, ["love_hate", "no_rating_column"],
     "Interactions without rating column: love/hate empty, legacy fields work"),
]


def build_cases() -> list[dict]:
    inter = create_test_interactions()
    user2id, item2id, _ = create_test_mappings(inter)
    meta = create_test_meta()
    cases = []
    for cid, uid, top_n, as_of, mode, tags, desc in SPECS:
        inp = {"user_id": uid, "top_n_categories": top_n}
        if as_of is not None:
            inp["as_of_timestamp"] = as_of
            inp["snapshot_mode"] = mode
        if mode == "untruncated" and "negative" in tags:
            expected = {"expect_error": "LeakageError"}
        else:
            # For u_no_rating, use interactions without rating column
            if uid == "u_no_rating":
                inter_for_case = get_interactions_without_rating(inter, uid)
            else:
                inter_for_case = inter

            # Use default love/hate thresholds matching memory.yaml
            expected = compute_memory_oracle(
                inter_for_case, uid, user2id, item2id, meta,
                top_n_categories=top_n,
                as_of_timestamp=as_of,
                love_min_rating=4,
                hate_max_rating=2,
                top_n_loved_items=10,
                top_n_hated_items=10
            )
            if as_of is not None:
                expected["leakage_probe"] = leakage_probe(
                    inter_for_case, uid, user2id, item2id, as_of, expected["n_interactions"])
        cases.append({"case_id": cid, "input": inp, "expected": expected,
                      "tags": ["correctness", *tags], "metadata": {"description": desc}})
    return cases


def render() -> str:
    return "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in build_cases())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed dataset differs")
    args = ap.parse_args()
    text = render()
    if args.check:
        same = DATASET_PATH.read_text(encoding="utf-8") == text
        print("dataset up to date" if same else "DATASET DRIFT: regenerate it")
        return 0 if same else 1
    DATASET_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {len(SPECS)} cases to {DATASET_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
