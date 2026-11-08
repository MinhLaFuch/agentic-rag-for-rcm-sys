"""Helper for adding --mock argument to scripts.

Code in package/ does not know mock vs real, only receives injected llm/tools/judge/data.
Only entry point (script) chooses real vs fake via --mock.
"""

import argparse


def add_mock_argument(parser: argparse.ArgumentParser) -> None:
    """Add --mock argument to parser for scripts that support mock mode."""
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock mode (fake LLM, fake tools, fake data) for testing without real resources",
    )


def check_mock_conditions(mock: bool, requires_llm: bool = True, requires_data: bool = True) -> None:
    """Check if required conditions are met for real mode; fail fast if not."""
    if mock:
        return  # Mock mode doesn't require real resources

    import os

    if requires_llm:
        if not os.environ.get("LLM_BASE_URL"):
            raise ValueError(
                "LLM_BASE_URL environment variable not set for real mode. "
                "Use --mock for testing without real LLM, or set LLM_BASE_URL."
            )

    if requires_data:
        # Add data path checks as needed
        pass
