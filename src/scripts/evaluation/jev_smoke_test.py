"""
Smoke test for real Jev provider integration.

Run this script with a real TYPESAFE_API_KEY to verify Jev connectivity.
Usage:
    TYPESAFE_API_KEY=your_key python scripts/evaluation/jev_smoke_test.py
"""

from __future__ import annotations

import os
import sys

from package.api import JevProvider
from package.evaluation.product_reply.evaluate_product_reply_with_jev import evaluate_product_reply_with_jev


def main() -> int:
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        print("ERROR: TYPESAFE_API_KEY environment variable not set")
        print("Usage: TYPESAFE_API_KEY=your_key python scripts/evaluation/jev_smoke_test.py")
        return 1

    print("Testing Jev provider connectivity...")
    print(f"API key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else '***'}")

    try:
        # Test 1: Simple Noul evaluation
        print("\n[Test 1] Simple Noul evaluation...")
        provider = JevProvider(api_key=api_key)
        result, usage = provider.evaluate_noul(
            state="Game A is an action game priced at $30.",
            instructions="Is this claim supported by the item data?",
        )
        print(f"  Result: {result}")
        print(f"  Usage: {usage}")
        provider.close()

        # Test 2: Full product reply evaluation
        print("\n[Test 2] Full product reply evaluation...")
        result = evaluate_product_reply_with_jev(
            request="I want an action game",
            items=[
                {
                    "item_id": "vg_001",
                    "title": "Action Game",
                    "main_category": "Action",
                    "price": 30.0,
                    "average_rating": 4.5,
                }
            ],
            answer="Action Game is an action game priced at $30.",
        )
        print(f"  Claims: {result['total_claims']}")
        print(f"  Unsupported: {result['unsupported_count']}")
        print(f"  Communication: {result.get('communication')}")
        print(f"  Evaluation state: {result['evaluation_state']}")
        print(f"  Usage: {result['usage']}")

        if result["evaluation_state"] == "success":
            print("\n✓ All smoke tests passed")
            return 0
        else:
            print(f"\n✗ Evaluation failed: {result['summary']}")
            return 1

    except Exception as e:
        print(f"\n✗ Smoke test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
