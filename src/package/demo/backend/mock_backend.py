"""MockBackend: phương án dự phòng khi demo lỗi (không dữ liệu/LLM/mạng)."""

from __future__ import annotations

from typing import Any

from ..view import DemoItem, DemoRequest, DemoResult, DemoTrace


# Dữ liệu mẫu cho MockBackend
_MOCK_ITEMS = [
    DemoItem(
        item_id="Video_Games::B00EXAMPLE1",
        domain="Video_Games",
        title="Example Game Controller",
        store="Amazon",
        price=49.99,
        average_rating=4.5,
        rating_number=1200,
        main_category="Electronics",
    ),
    DemoItem(
        item_id="Toys_and_Games::B00EXAMPLE2",
        domain="Toys_and_Games",
        title="Example Building Blocks Set",
        store="Amazon",
        price=29.99,
        average_rating=4.7,
        rating_number=850,
        main_category="Toys",
    ),
    DemoItem(
        item_id="Electronics::B00EXAMPLE3",
        domain="Electronics",
        title="Example Wireless Headphones",
        store="Amazon",
        price=79.99,
        average_rating=4.3,
        rating_number=2100,
        main_category="Electronics",
    ),
]

_MOCK_TRAILS = {
    "ok": DemoTrace(
        plan=[{"tool": "QueryTool", "args": {"item_ids": ["Video_Games::B00EXAMPLE1"]}}],
        steps=[{"tool": "QueryTool", "ok": True, "error": None, "latency_seconds": 0.1}],
        ask_user=None,
        reflections=0,
        first_attempt_ok=True,
        truncated=False,
        usage={"attempts": 1, "prompt_tokens": 100, "completion_tokens": 50, "latency_seconds": 0.5},
    ),
    "ask_user": DemoTrace(
        plan=[],
        steps=[],
        ask_user="Bạn muốn tìm sản phẩm thuộc danh mục nào?",
        reflections=0,
        first_attempt_ok=True,
        truncated=False,
        usage={"attempts": 1, "prompt_tokens": 50, "completion_tokens": 20, "latency_seconds": 0.3},
    ),
    "no_result": DemoTrace(
        plan=[{"tool": "SemanticSearchTool", "args": {"query": "nonexistent"}}],
        steps=[{"tool": "SemanticSearchTool", "ok": True, "error": None, "latency_seconds": 0.2}],
        ask_user=None,
        reflections=0,
        first_attempt_ok=True,
        truncated=False,
        usage={"attempts": 1, "prompt_tokens": 80, "completion_tokens": 30, "latency_seconds": 0.4},
    ),
    "tool_error": DemoTrace(
        plan=[{"tool": "QueryTool", "args": {"item_ids": ["invalid"]}}],
        steps=[{"tool": "QueryTool", "ok": False, "error": "Item not found", "latency_seconds": 0.1}],
        ask_user=None,
        reflections=0,
        first_attempt_ok=False,
        truncated=False,
        usage={"attempts": 1, "prompt_tokens": 60, "completion_tokens": 10, "latency_seconds": 0.2},
    ),
}


class MockBackend:
    """Backend giả, trả kết quả có sẵn cho demo (không cần dữ liệu/LLM/mạng)."""

    def __init__(self) -> None:
        self._request_count = 0

    def respond(self, request: DemoRequest) -> DemoResult:
        """Xử lý request và trả kết quả mẫu."""
        self._request_count += 1

        # Chọn status dựa trên request_count để xoay vòng qua 4 trạng thái
        statuses = ["ok", "ask_user", "no_result", "tool_error"]
        status = statuses[(self._request_count - 1) % len(statuses)]

        if status == "ok":
            return DemoResult(
                status="ok",
                text="Dựa trên yêu cầu của bạn, tôi đã tìm thấy các sản phẩm sau:",
                items=_MOCK_ITEMS[:2],
                trace=_MOCK_TRAILS["ok"],
                usage=dict(_MOCK_TRAILS["ok"].usage),
                error=None,
            )
        elif status == "ask_user":
            return DemoResult(
                status="ask_user",
                text="Tôi cần thêm thông tin để gợi ý chính xác hơn.",
                items=[],
                trace=_MOCK_TRAILS["ask_user"],
                usage=dict(_MOCK_TRAILS["ask_user"].usage),
                error=None,
            )
        elif status == "no_result":
            return DemoResult(
                status="no_result",
                text="Không tìm thấy sản phẩm phù hợp với yêu cầu của bạn.",
                items=[],
                trace=_MOCK_TRAILS["no_result"],
                usage=dict(_MOCK_TRAILS["no_result"].usage),
                error=None,
            )
        else:  # tool_error
            return DemoResult(
                status="tool_error",
                text="Có lỗi xảy ra khi xử lý yêu cầu. Vui lòng thử lại.",
                items=[],
                trace=_MOCK_TRAILS["tool_error"],
                usage=dict(_MOCK_TRAILS["tool_error"].usage),
                error="Lỗi tool: Item not found",
            )
