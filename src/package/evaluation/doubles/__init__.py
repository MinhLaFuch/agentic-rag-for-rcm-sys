"""Test doubles for tools, LLM, and judge.

This module contains fake implementations used for testing and mock mode.
These are intentional test doubles, not production code.
"""

from .fake_tools import (
    FakeFilterTool,
    FakeSearchTool,
    FakeRankTool,
    FakeSimilarTool,
    FakeLookupTool,
)
from .fake_llm import ScriptedLLM
from .fake_judge import ScriptedJudge

__all__ = [
    "FakeFilterTool",
    "FakeSearchTool",
    "FakeRankTool",
    "FakeSimilarTool",
    "FakeLookupTool",
    "ScriptedLLM",
    "ScriptedJudge",
]
