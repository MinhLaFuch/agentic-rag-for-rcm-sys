"""Demo UI cho hệ gợi ý sản phẩm bằng LLM agent."""

from ._limits import get_demo_limits
from .adapter import adapt_from_inference, adapt_from_plan_executor, adapt_from_plan_executor_error
from .backend import LiveBackend, MockBackend
from .samples import sample_requests, sample_users
from .view import DemoItem, DemoRequest, DemoResult, DemoTrace, format_items, format_trace, status_badge

__all__ = [
    "DemoItem",
    "DemoRequest",
    "DemoResult",
    "DemoTrace",
    "adapt_from_plan_executor",
    "adapt_from_plan_executor_error",
    "adapt_from_inference",
    "format_items",
    "format_trace",
    "status_badge",
    "MockBackend",
    "LiveBackend",
    "sample_requests",
    "sample_users",
    "get_demo_limits",
]
