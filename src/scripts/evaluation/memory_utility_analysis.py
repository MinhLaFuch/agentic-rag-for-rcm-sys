"""CLI script for Memory UTILITY analysis.

Thin wrapper over package.evaluation.component.benchmarks.memory_utility —
không nhận tham số CLI. Mọi tham số (kể cả dirs/metrics input) đọc từ
configs/eval/memory_utility.yaml, output dir từ data_paths.outputs.memory_utility.

    PYTHONPATH=. python scripts/evaluation/memory_utility_analysis.py
"""

from __future__ import annotations

import sys

from package.evaluation.component.benchmarks.memory_utility import memory_utility


def main(argv: list[str] | None = None) -> int:
    return memory_utility(argv)


if __name__ == "__main__":
    sys.exit(main())
