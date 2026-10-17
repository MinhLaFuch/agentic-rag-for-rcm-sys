"""Dataclass of one evaluation request."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentRequest:
    request_id: str
    kind: str  # one of KINDS
    segment: str  # cold | sparse | warm | none
    text: str  # what the user "says" to the agent
    user_id: str | None = None
    user_idx: int | None = None
    seed_item_id: str | None = None  # "similar": the user's most recent fit item
    targets: list[int] = field(default_factory=list)  # relevant held-out item_idx
    price_max: float | None = None  # "constrained"
    category: str | None = None  # "constrained" / "cold_text"
    oracle: bool = False  # True when constraints were derived from held-out items

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
