"""Negative control for the Jev judge: hand-written answers, known verdicts.

The grounding component benchmark cannot contain deliberately-wrong answers
(template mode cannot hallucinate), so judge discrimination is verified here
instead — OUTSIDE pytest, run manually when TYPESAFE_API_KEY is available:

    PYTHONPATH=. python scripts/evaluation/jev_negative_control.py

Each case pairs an answer with the verdict a correct judge MUST return.
Exit code 0 = judge discriminated every case; non-zero = judge missed a
fabricated claim or flagged a faithful one (judge problem, not benchmark problem).
"""

from __future__ import annotations

import sys

from package.evaluation.product_reply.evaluate_product_reply_with_jev import (
    evaluate_product_reply_with_jev,
)

ITEMS = [
    {
        "item_id": "vg_001",
        "domain": "Video_Games",
        "title": "Super Action Game",
        "store": "Ninja Games",
        "price": 19.99,
        "average_rating": 4.2,
        "rating_number": 130,
        "main_category": "Action",
    },
    {
        "item_id": "vg_002",
        "domain": "Video_Games",
        "title": "Puzzle Master",
        "store": "Brainy",
        "price": 9.99,
        "average_rating": 4.6,
        "rating_number": 512,
        "main_category": "Puzzle",
    },
]

# (name, request, answer, expect_unsupported_claims: bool)
# Faithful answers only restate item fields -> every claim must be supported.
# Fabricated answers add a claim absent from / contradicting the fields.
CASES = [
    (
        "faithful_price_rating",
        "show me games",
        "1. Super Action Game (vg_001)\n   Giá: $19.99 · Đánh giá: 4.2/5 (130 lượt) · Nhà bán: Ninja Games",
        False,
    ),
    (
        "faithful_null_field",
        "show me games",
        "1. Puzzle Master (vg_002)\n   Giá: $9.99 · Đánh giá: 4.6/5 · Nhà bán: Brainy",
        False,
    ),
    (
        "fabricated_price",
        "show me games",
        "1. Super Action Game (vg_001)\n   Giá: $5.00 · Đánh giá: 4.2/5 · Nhà bán: Ninja Games",
        True,
    ),
    (
        "fabricated_category",
        "show me games",
        "1. Super Action Game (vg_001) là game đua xe hàng đầu\n   Giá: $19.99",
        True,
    ),
    (
        "fabricated_item",
        "show me games",
        "1. Super Action Game (vg_001) — giá rẻ nhất thị trường\n2. Zelda TOTK (vg_999) — đại ca của dòng game",
        True,
    ),
]


def main() -> int:
    failures = []
    for name, request, answer, expect_unsupported in CASES:
        result = evaluate_product_reply_with_jev(request=request, items=ITEMS, answer=answer)
        state = result.get("evaluation_state")
        if state == "provider_error":
            print(f"[SKIP] {name}: Jev provider error ({result.get('summary')}) — set TYPESAFE_API_KEY")
            return 2
        unsupported = int(result.get("unsupported_count", 0))
        supported = int(result.get("supported_count", 0))
        ok = (unsupported > 0) if expect_unsupported else (unsupported == 0 and supported > 0)
        status = "PASS" if ok else "FAIL"
        print(
            f"[{status}] {name}: supported={supported} unsupported={unsupported} "
            f"judge_errors={result.get('judge_error_count')} state={state}"
        )
        if not ok:
            failures.append(name)
    if failures:
        print(f"\nJudge failed to discriminate: {failures}")
        return 1
    print("\nAll negative-control cases discriminated correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
