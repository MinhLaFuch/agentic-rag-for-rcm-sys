"""Select realistic proxy requests or target-informed oracle requests explicitly."""

from __future__ import annotations

from ._dataclass import AgentRequest


def filter_requests_by_scope(requests: list[AgentRequest], scope: str) -> list[AgentRequest]:
    """Select requests according to their target-information scope."""
    if scope == "all":
        return list(requests)
    if scope == "realistic":
        return [request for request in requests if not request.oracle]
    if scope == "oracle":
        return [request for request in requests if request.oracle]
    raise ValueError("scope must be one of: realistic, oracle, all")
