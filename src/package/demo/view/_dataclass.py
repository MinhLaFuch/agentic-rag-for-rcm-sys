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
    """Vết thực thi: plan JSON, từng step, reflections, usage, và thông tin inference."""
    plan: list[dict[str, Any]]
    steps: list[dict[str, Any]]  # mỗi step có: tool, ok, error, latency_seconds, args, output_summary
    ask_user: str | None
    reflections: int
    first_attempt_ok: bool
    truncated: bool
    usage: dict[str, Any]
    inference: dict[str, Any] | None = None  # Thông tin từ Inference: composer, grounded, fallback_reason, reason, usage


@dataclass
class DemoResult:
    """Kết quả trả về cho UI (view model)."""
    status: str  # "ok", "ask_user", "no_result", "tool_error"
    text: str  # câu trả lời (do hàm mẫu hoặc Inference tổng hợp)
    items: list[DemoItem]
    trace: DemoTrace | None
    usage: dict[str, Any]
    error: str | None  # thông báo lỗi rút gọn (chỉ khi status="tool_error")
    memory: MemoryView | None = None  # view của memory tool cho UI


@dataclass
class DemoProfile:
    """Profile người dùng cho demo UI."""
    profile_id: str
    label: str
    description: str
    user_id: str | None  # None = blank profile (new user)
    segment: str  # "blank", "cold", "sparse", "warm", hoặc custom


@dataclass
class MemoryView:
    """View của memory tool cho UI."""
    enabled: bool  # memory toggle on/off
    called: bool  # planner có gọi MemoryTool không
    n_calls: int  # số lần MemoryTool được gọi
    before: dict[str, Any] | None  # snapshot trước turn (MemoryTool output shape)
    after: dict[str, Any] | None  # snapshot sau turn (MemoryTool output shape)
    agent_calls: list[dict[str, Any]]  # từng step MemoryTool trong plan
    consumed_by: list[dict[str, Any]]  # step nào đã dùng output của MemoryTool ($<n>)


@dataclass
class DemoRequest:
    """Yêu cầu từ UI."""
    user_id: str | None
    text: str
    reflect_rounds: int  # 0 hoặc 1
    use_memory: bool
    mode: str  # "planner" hoặc "type1"
    inference_mode: str = "llm"  # "llm" hoặc "template"
    profile_id: str | None = None  # profile được chọn (để tương lai)
