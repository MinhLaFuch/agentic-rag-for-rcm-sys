"""Build provenance information for an experiment run (hashes of prompts, tool schemas, git state, limits)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from typing import Any

from ..agents._limits import get_agent_limits
from ..agents.planner._prompt import SYSTEM_PROMPT as PLANNER_SYSTEM_PROMPT
from ..agents.toolkit.build_tool_prompt import build_tool_prompt
from ..inference._limits import get_inference_limits
from ..inference.compose._prompt import SYSTEM_PROMPT as INFERENCE_SYSTEM_PROMPT
from ..tools.base import Tool


def _sha256(text: str) -> str:
    """Return SHA256 hash of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_sha256(obj: Any) -> str:
    """Return SHA256 hash of a JSON-serializable object with stable key ordering."""
    return _sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False))


def _git_info() -> tuple[str | None, bool]:
    """Return (git_commit_sha, dirty) or (None, False) if git is unavailable."""
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(status)
        return commit, dirty
    except (subprocess.SubprocessError, FileNotFoundError):
        return None, False


def build_run_provenance(
    planner_tools: list[Tool],
    memory_tools: list[Tool] | None = None,
) -> dict[str, Any]:
    """
    Build provenance dict for an experiment run.

    Args:
        planner_tools: Tools available to the planner agent
        memory_tools: Tools available to the planner_memory agent (if different)

    Returns:
        Dict with keys:
        - planner_prompt_sha256: hash of formatted planner system prompt
        - planner_memory_prompt_sha256: hash of formatted planner_memory system prompt (or None if same as planner)
        - inference_prompt_sha256: hash of inference system prompt
        - tool_schema_sha256: hash of tool schemas (name, input_schema, output_schema)
        - git_commit: git commit SHA or None
        - git_dirty: True if working tree has uncommitted changes
        - agent_limits: planner limits (temperature, max_tokens, max_steps, plan_retries, reflect_rounds, llm_retries)
        - inference_limits: inference limits (temperature, max_tokens, llm_retries, check_numbers, price_tolerance)
    """
    # Hash planner prompts (formatted with tools)
    planner_prompt = PLANNER_SYSTEM_PROMPT.format(tools=build_tool_prompt(planner_tools))
    planner_prompt_sha256 = _sha256(planner_prompt)

    planner_memory_prompt_sha256 = None
    if memory_tools is not None and memory_tools != planner_tools:
        memory_prompt = PLANNER_SYSTEM_PROMPT.format(tools=build_tool_prompt(memory_tools))
        planner_memory_prompt_sha256 = _sha256(memory_prompt)

    # Hash inference prompt
    inference_prompt_sha256 = _sha256(INFERENCE_SYSTEM_PROMPT)

    # Hash tool schemas (all tools the planner might see)
    all_tools = list(dict.fromkeys(planner_tools + (memory_tools or [])))  # deduplicate
    tool_schemas = [
        {
            "name": t.name,
            "input_schema": t.input_schema,
            "output_schema": t.output_schema,
        }
        for t in all_tools
    ]
    tool_schema_sha256 = _json_sha256(tool_schemas)

    # Git info
    git_commit, git_dirty = _git_info()

    # Agent limits
    agent_limits = get_agent_limits()
    agent_limits_dict = {
        "temperature": agent_limits.temperature,
        "max_tokens": agent_limits.max_tokens,
        "max_steps": agent_limits.max_steps,
        "plan_retries": agent_limits.plan_retries,
        "reflect_rounds": agent_limits.reflect_rounds,
        "llm_retries": None,  # Not in agent limits, will be added if needed
    }

    # Inference limits
    inference_limits = get_inference_limits()
    inference_limits_dict = {
        "temperature": inference_limits.temperature,
        "max_tokens": inference_limits.max_tokens,
        "llm_retries": inference_limits.llm_retries,
        "check_numbers": inference_limits.check_numbers,
        "price_tolerance": inference_limits.price_tolerance,
    }

    return {
        "planner_prompt_sha256": planner_prompt_sha256,
        "planner_memory_prompt_sha256": planner_memory_prompt_sha256,
        "inference_prompt_sha256": inference_prompt_sha256,
        "tool_schema_sha256": tool_schema_sha256,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "agent_limits": agent_limits_dict,
        "inference_limits": inference_limits_dict,
    }
