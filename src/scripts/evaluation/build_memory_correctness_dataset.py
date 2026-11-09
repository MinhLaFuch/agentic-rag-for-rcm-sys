"""CLI script to generate or check the memory correctness dataset.

    python -m scripts.evaluation.build_memory_correctness_dataset          # (re)write
    python -m scripts.evaluation.build_memory_correctness_dataset --check  # fail on drift
"""

from __future__ import annotations

import argparse
import sys

from package.evaluation.component.benchmarks import DATASET_PATH, render


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
    print(f"wrote {len(text.splitlines())} cases to {DATASET_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())