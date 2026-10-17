from __future__ import annotations

from dataclasses import replace

from ...api import LLMProvider
from .._dataclass import AgentOutcome, Answer
from .._limits import get_inference_limits
from .._schema import MODES
from .compose_llm import compose_llm
from .compose_template import compose_template


def compose_answer(
    outcome: AgentOutcome,
    llm: LLMProvider | None = None,
    *,
    mode: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    llm_retries: int | None = None,
    check_numbers: bool | None = None,
    price_tolerance: float | None = None,
) -> Answer:
    """
    The final answer for an agent's outcome. Defaults come from configs/agent/inference.yaml.
    ask_user / no_result / tool_error and mode "template" never call the LLM; mode "llm" without a provider
    falls back to the template (fallback_reason "no_llm"). Presents only: it never changes the agent's items.
    """
    limits = get_inference_limits()
    mode = limits.mode if mode is None else mode
    if mode not in MODES:
        raise ValueError(f"mode must be one of {list(MODES)}, got {mode!r}")
    template = compose_template(outcome)
    if template.status != "ok" or mode == "template":
        return template
    if llm is None:
        return replace(template, fallback_reason="no_llm")
    return compose_llm(
        outcome, llm,
        max_tokens=limits.max_tokens if max_tokens is None else max_tokens,
        temperature=limits.temperature if temperature is None else temperature,
        llm_retries=limits.llm_retries if llm_retries is None else llm_retries,
        check_numbers=limits.check_numbers if check_numbers is None else check_numbers,
        price_tolerance=limits.price_tolerance if price_tolerance is None else price_tolerance,
    )
