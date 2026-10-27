"""View model cho demo UI: những gì UI hiển thị, tách biệt từ tầng Inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DemoItem:
    """Một item gợi ý hiển thị trên UI."""
    item_id: str
    domain: str
    title: str
    store: str | None
    price: float | None
    average_rating: float | None
    rating_number: int | None
    main_category: str | None


@dataclass
class DemoTrace:
    """Vết thực thi: plan JSON, từng step, reflections, usage."""
    plan: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    ask_user: str | None
    reflections: int
    first_attempt_ok: bool
    truncated: bool
    usage: dict[str, Any]


@dataclass
class DemoResult:
    """Kết quả trả về cho UI (view model)."""
    status: str  # "ok", "ask_user", "no_result", "tool_error"
    text: str  # câu trả lời (do hàm mẫu hoặc Inference tổng hợp)
    items: list[DemoItem]
    trace: DemoTrace | None
    usage: dict[str, Any]
    error: str | None  # thông báo lỗi rút gọn (chỉ khi status="tool_error")
    recommendation_source: str | None = None


@dataclass
class DemoRequest:
    """Yêu cầu từ UI."""
    user_id: str | None
    text: str
    reflect_rounds: int  # 0 hoặc 1
    use_memory: bool
    mode: str  # "planner" hoặc "type1"
    intent_query: str | None = None
    intent_filters: dict[str, Any] | None = None
