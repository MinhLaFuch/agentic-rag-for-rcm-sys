"""Runtime factory for real vs mock mode.

Code in package/ does not know mock vs real, only receives injected llm/tools/judge/data.
This factory is the single entry point for scripts to get real or fake components.
"""

from typing import Any
from pathlib import Path

from package.config.load_config import load_config
from package.api import build_llm_provider
from package.evaluation.doubles import (
    FakeFilterTool,
    FakeSearchTool,
    FakeRankTool,
    FakeSimilarTool,
    FakeLookupTool,
    ScriptedLLM,
    ScriptedJudge,
)


def build_runtime(
    mock: bool = False,
    requires_llm: bool = True,
    requires_data: bool = True,
) -> dict[str, Any]:
    """
    Build runtime components (llm, tools, judge, data) based on mock flag.

    Args:
        mock: If True, use fake components. If False, use real components.
        requires_llm: If True, real mode requires LLM_BASE_URL.
        requires_data: If True, real mode requires data paths.

    Returns:
        dict with keys: llm, tools, judge, data, mode ("mock" or "real")

    Raises:
        ValueError: If real mode conditions are not met.
    """
    import os

    if mock:
        print("⚠️  MOCK MODE ACTIVE - Using fake LLM, fake tools, fake data")
        return {
            "llm": ScriptedLLM(),
            "tools": [
                FakeFilterTool(),
                FakeSearchTool(),
                FakeRankTool(),
                FakeSimilarTool(),
                FakeLookupTool(),
            ],
            "judge": ScriptedJudge(),
            "data": None,  # Fake data would be created per-script
            "mode": "mock",
        }
    else:
        # Real mode - check conditions
        if requires_llm and not os.environ.get("LLM_BASE_URL"):
            raise ValueError(
                "LLM_BASE_URL environment variable not set for real mode. "
                "Use --mock for testing without real LLM, or set LLM_BASE_URL."
            )

        if requires_data:
            # Data path checks would go here per-script
            pass

        print("✓ REAL MODE - Using real LLM, real tools, real data")
        llm_config = load_config("agent/llm")
        llm = build_llm_provider(llm_config)

        # Real tools would be built per-script with real data
        return {
            "llm": llm,
            "tools": None,  # Real tools built per-script
            "judge": None,  # Real judge built per-script
            "data": None,  # Real data loaded per-script
            "mode": "real",
        }
