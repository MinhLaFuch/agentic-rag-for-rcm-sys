"""Demo UI cho hệ gợi ý sản phẩm bằng LLM agent."""

from ._view_model import DemoItem, DemoRequest, DemoResult, DemoTrace
from ._adapter import adapt_from_plan_executor, adapt_from_plan_executor_error, adapt_from_inference
from ._formatter import format_items, format_trace, status_badge
from ._mock_backend import MockBackend
from ._live_backend import LiveBackend
from ._samples import sample_requests, sample_users
from ._limits import get_demo_limits

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
