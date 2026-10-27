"""
Evaluate product recommendation assistant replies using Jev (TypeSafe AI) for judgments.

This script uses Jev's structured decision capabilities (Noul/Score) instead of
generating free-form text, providing more reliable and explainable evaluations.

Usage:
    PYTHONPATH=. python scripts/evaluation/evaluate_with_jev.py --input-file data.jsonl
    PYTHONPATH=. python scripts/evaluation/evaluate_with_jev.py --request "request text" --items-file items.json --answer "answer text"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from package.evaluation.jev_product_evaluator import evaluate_product_reply_with_jev


def load_jsonl(file_path: Path) -> list[dict]:
    """Load data from a JSONL file."""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def load_json(file_path: Path) -> dict | list:
    """Load data from a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate product recommendation assistant replies using Jev (TypeSafe AI)"
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        help="JSONL file with entries containing 'request', 'items', and 'answer' fields"
    )
    parser.add_argument(
        "--request",
        type=str,
        help="User request text (use if not using --input-file)"
    )
    parser.add_argument(
        "--items-file",
        type=Path,
        help="JSON file containing the items array (use if not using --input-file)"
    )
    parser.add_argument(
        "--answer",
        type=str,
        help="Assistant's answer text (use if not using --input-file)"
    )
    parser.add_argument(
        "--config-file",
        type=Path,
        default=None,
        help="Path to judge.yaml config. If not provided, uses configs/agent/judge.yaml"
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Output file for evaluation results (JSON format). If not provided, prints to stdout."
    )

    args = parser.parse_args()

    # Validate arguments
    if args.input_file:
        if args.request or args.items_file or args.answer:
            print("Error: Cannot use --input-file together with --request/--items-file/--answer", file=sys.stderr)
            return 1

        data = load_jsonl(args.input_file)
        results = []
        for i, entry in enumerate(data):
            if not all(key in entry for key in ["request", "items", "answer"]):
                print(f"Error: Entry {i} missing required fields: {entry}", file=sys.stderr)
                return 1

            print(f"Evaluating entry {i+1}/{len(data)}...", file=sys.stderr)
            result = evaluate_product_reply_with_jev(
                request=entry["request"],
                items=entry["items"],
                answer=entry["answer"],
                config_path=args.config_file,
            )
            results.append(result)

        output = results if len(results) > 1 else results[0] if results else {}

    else:
        if not (args.request and args.items_file and args.answer):
            print("Error: Must provide --request, --items-file, and --answer when not using --input-file", file=sys.stderr)
            return 1

        items = load_json(args.items_file)
        if not isinstance(items, list):
            print("Error: Items file must contain a JSON array", file=sys.stderr)
            return 1

        output = evaluate_product_reply_with_jev(
            request=args.request,
            items=items,
            answer=args.answer,
            config_path=args.config_file,
        )

    # Output results
    output_json = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output_file:
        with open(args.output_file, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"Results written to {args.output_file}")
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
