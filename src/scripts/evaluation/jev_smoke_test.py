"""
Smoke test for real Jev provider integration.

Reads configs/eval/judge.yaml (JEV_API_KEY / JEV_BASE_URL env interpolation,
CONFIG_OVERLAY_PATH aware) — works with TypeSafe direct or OpenRouter System One.

Usage:
    JEV_API_KEY=your_key JEV_BASE_URL=https://openrouter.ai/api \
        python scripts/evaluation/jev_smoke_test.py
"""

from __future__ import annotations

import os
import sys

from package.api import JevProvider
from package.config import load_config
from package.evaluation.product_reply.evaluate_product_reply_with_jev import evaluate_product_reply_with_jev


def main() -> int:
    config = load_config("eval/judge")
    api_key = config.get("api_key") or None  # "" -> None so JevProvider env fallback applies
    if not api_key and not any(
        os.environ.get(k) for k in ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY")
    ):
        print("ERROR: no judge API key — set JEV_API_KEY (or TYPESAFE_API_KEY / OPENROUTER_API_KEY)")
        return 1

    print("Testing Jev provider connectivity...")
    print(f"base_url: {config.get('base_url')}")
    print(f"model: {config.get('model')}")

    try:
        # Test 1: Simple Noul evaluation
        print("\n[Test 1] Simple Noul evaluation...")
        provider = JevProvider(
            api_key=api_key,  # None -> provider falls back to TYPESAFE/OPENROUTER env
            model=config.get("model", "jev-latest"),
            base_url=config.get("base_url", "https://api.typesafe.ai"),
            timeout=config.get("timeout_seconds"),
        )
        key = provider.api_key
        print(f"API key: {key[:8]}...{key[-4:] if len(key) > 12 else '***'}")
        result, usage = provider.evaluate_noul(
            state="Game A is an action game priced at $30.",
            instructions="Is this claim supported by the item data?",
        )
        print(f"  Result: {result}")
        print(f"  Usage: {usage}")
        provider.close()

        # Test 2: Full product reply evaluation (loads eval/judge itself)
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
