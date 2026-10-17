"""Adapter khi PlanExecutor ném ngoại lệ."""

from __future__ import annotations

from ._dataclass import DemoRequest, DemoResult
from ._helper import _generate_text_for_status
from ._limits import get_demo_limits


def adapt_from_plan_executor_error(
    exc: Exception,
    request: DemoRequest,
) -> DemoResult:
    """Adapter khi PlanExecutor ném ngoại lệ."""
    limits = get_demo_limits()
    error_msg = f"{type(exc).__name__}: {exc}"[:limits.max_error_length]
    status = "tool_error"
    text = _generate_text_for_status(status, request)
    return DemoResult(
        status=status,
        text=text,
        items=[],
        trace=None,
        usage={},
        error=error_msg,
    )
