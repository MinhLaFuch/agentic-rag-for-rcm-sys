"""Main CLI dispatcher for component benchmarks."""

from __future__ import annotations

import sys


def run() -> None:
    """Dispatch to appropriate subcommand."""
    if len(sys.argv) > 1 and sys.argv[1] == "regress":
        # Remove "regress" from args before parsing
        sys.argv.pop(1)
        from .run_regression_cli import run_regression_cli
        run_regression_cli()
    else:
        from .run_benchmark_cli import run_benchmark_cli
        run_benchmark_cli()


if __name__ == "__main__":
    run()
