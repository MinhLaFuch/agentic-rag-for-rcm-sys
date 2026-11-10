"""CLI script for component benchmarks + unified report.

Thin wrapper over package.evaluation.component.run_component_benchmarks —
runs every benchmark listed in configs/eval/component_benchmarks.yaml, then
the multi_turn step (skipped_no_credentials without LLM creds), and writes
unified_report_<ts>.json/.md to the component_benchmarks output dir.

    PYTHONPATH=. python scripts/evaluation/run_component_benchmarks.py

Equivalent to: python -m package.evaluation.component._run_all
"""

from __future__ import annotations

import sys

from package.evaluation.component import run_component_benchmarks


def main() -> int:
    return run_component_benchmarks()


if __name__ == "__main__":
    sys.exit(main())
