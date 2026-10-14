"""AgentOutcome (what an agent produced) and Answer (what the user is shown)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentOutcome:
    request_text: str
    items: list[dict[str, Any]] = field(default_factory=list)  # agent order, de-duplicated, cut to max_items; keys = ITEM_FIELDS
    question: str | None = None  # clarifying question of the planner (ask_user)
    errors: list[dict[str, str]] = field(default_factory=list)  # {"tool", "error"}; for logs/reason only, never shown to the user
    invented_ids: list[str] = field(default_factory=list)
    cold_start: bool | None = None  # Type1Agent only
    n_steps: int = 0  # steps that ran (0 + a question = the agent asked back)


@dataclass
class Answer:
    status: str  # one of STATUSES
    text: str
    items: list[dict[str, Any]] = field(default_factory=list)  # exactly the items `text` presents (agent order); [] unless status == "ok"
    grounded: bool = True  # text passed the grounding checks (True where there is nothing to check)
    composer: str = "template"  # "llm" | "template"
    fallback_reason: str | None = None  # only when the LLM should have written the text but the template did
    usage: dict[str, Any] = field(default_factory=dict)  # Inference's own LLM calls (attempts include a call that failed at the provider)
    reason: str | None = None  # why this status (logs): tool_error detail, "partial: ...", "question ignored: ..."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
