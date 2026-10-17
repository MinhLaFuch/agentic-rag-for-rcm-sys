from __future__ import annotations

import json
from dataclasses import replace

from ..api import LLMMessage, LLMProvider
from ..api import LLMProviderError
from ._dataclass import AgentOutcome, Answer
from ._helper import check_grounding, cut, item_view, parse_llm_reply
from ._prompt import RETRY_NOTICE, SYSTEM_PROMPT
from .compose_template import compose_template


def compose_llm(
    outcome: AgentOutcome,
    llm: LLMProvider,
    *,
    max_tokens: int,
    temperature: float,
    llm_retries: int,
    check_numbers: bool,
    price_tolerance: float,
) -> Answer:
    """
    Ask the LLM to present the outcome's items, check the reply against the data, retry up to `llm_retries` times
    with the reason, then fall back to the template (fallback_reason says why). Never raises: a provider error
    must not cost the result the agent already has. Only status "ok" reaches the LLM; any other outcome gets its fixed text.
    usage counts every call of this function (a call that failed at the provider counts as an attempt, with 0 tokens).
    """
    template = compose_template(outcome)
    if template.status != "ok":
        return template
    usage = dict(template.usage)
    data = {"request": outcome.request_text, "items": [item_view(i) for i in outcome.items]}
    messages = [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(role="user", content="Request and products:\n" + json.dumps(data, ensure_ascii=False)),
    ]
    reason = "invalid_json: no reply"
    for attempt in range(llm_retries + 1):
        try:
            resp = llm.complete(messages, temperature=temperature, max_tokens=max_tokens, response_format_json=True)
        except LLMProviderError as exc:
            usage["attempts"] += 1
            return replace(template, fallback_reason=cut(f"provider_error: {exc}"), usage=usage)
        usage["attempts"] += 1
        usage["prompt_tokens"] += resp.prompt_tokens or 0
        usage["completion_tokens"] += resp.completion_tokens or 0
        usage["latency_seconds"] += resp.latency_seconds or 0.0
        try:
            text, mentioned = parse_llm_reply(resp.text)
            problem = check_grounding(text, mentioned, outcome, check_numbers=check_numbers, price_tolerance=price_tolerance)
            if problem is None:
                return Answer(status="ok", text=text, items=[dict(i) for i in outcome.items], grounded=True, composer="llm",
                              usage=usage, reason=template.reason)
            error, reason = problem, f"ungrounded: {problem}"
        except ValueError as exc:
            error, reason = str(exc), str(exc)
        if attempt == llm_retries:
            break
        messages = [*messages, LLMMessage(role="assistant", content=resp.text), LLMMessage(role="user", content=RETRY_NOTICE.format(error=error))]
    return replace(template, fallback_reason=cut(reason), usage=usage)
