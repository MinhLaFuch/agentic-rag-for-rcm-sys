"""MockBackend: phương án dự phòng khi demo lỗi (không dữ liệu/LLM/mạng)."""

from __future__ import annotations

from typing import Any

from ..view import DemoItem, DemoProfile, MemoryView, DemoRequest, DemoResult, DemoTrace


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
        inference={"composer": "template", "grounded": True, "fallback_reason": None, "reason": None, "usage": {"attempts": 0}},
    ),
    "ask_user": DemoTrace(
        plan=[],
        steps=[],
        ask_user="Bạn muốn tìm sản phẩm thuộc danh mục nào?",
        reflections=0,
        first_attempt_ok=True,
        truncated=False,
        usage={"attempts": 1, "prompt_tokens": 50, "completion_tokens": 20, "latency_seconds": 0.3},
        inference={"composer": "template", "grounded": True, "fallback_reason": None, "reason": "ask_user", "usage": {"attempts": 0}},
    ),
    "no_result": DemoTrace(
        plan=[{"tool": "SemanticSearchTool", "args": {"query": "nonexistent"}}],
        steps=[{"tool": "SemanticSearchTool", "ok": True, "error": None, "latency_seconds": 0.2}],
        ask_user=None,
        reflections=0,
        first_attempt_ok=True,
        truncated=False,
        usage={"attempts": 1, "prompt_tokens": 80, "completion_tokens": 30, "latency_seconds": 0.4},
        inference={"composer": "template", "grounded": True, "fallback_reason": None, "reason": "no_result", "usage": {"attempts": 0}},
    ),
    "tool_error": DemoTrace(
        plan=[{"tool": "QueryTool", "args": {"item_ids": ["invalid"]}}],
        steps=[{"tool": "QueryTool", "ok": False, "error": "Item not found", "latency_seconds": 0.1}],
        ask_user=None,
        reflections=0,
        first_attempt_ok=False,
        truncated=False,
        usage={"attempts": 1, "prompt_tokens": 60, "completion_tokens": 10, "latency_seconds": 0.2},
        inference={"composer": "template", "grounded": True, "fallback_reason": None, "reason": "tool_error", "usage": {"attempts": 0}},
    ),
}


class MockBackend:
    """Backend giả, trả kết quả có sẵn cho demo (không cần dữ liệu/LLM/mạng)."""

    def __init__(self) -> None:
        self._request_count = 0

    def get_profiles(self) -> list[DemoProfile]:
        """Trả về fake profiles cho mock mode."""
        return [
            DemoProfile(
                profile_id="blank",
                label="New user (no history)",
                description="Blank profile for testing cold-start behavior",
                user_id=None,
                segment="blank",
            ),
            DemoProfile(
                profile_id="mock_cold",
                label="Cold user (0 interactions)",
                description="Mock cold user with no history",
                user_id="mock_cold_user",
                segment="cold",
            ),
            DemoProfile(
                profile_id="mock_sparse",
                label="Sparse user (3 interactions)",
                description="Mock sparse user with few interactions",
                user_id="mock_sparse_user",
                segment="sparse",
            ),
            DemoProfile(
                profile_id="mock_warm",
                label="Warm user (20 interactions)",
                description="Mock warm user with many interactions",
                user_id="mock_warm_user",
                segment="warm",
            ),
        ]

    def respond(self, request: DemoRequest) -> DemoResult:
        """Xử lý request và trả kết quả mẫu."""
        self._request_count += 1

        # Chọn status dựa trên request_count để xoay vòng qua 4 trạng thái
        statuses = ["ok", "ask_user", "no_result", "tool_error"]
        status = statuses[(self._request_count - 1) % len(statuses)]

        # inference_mode được nhận nhưng không ảnh hưởng mock (không có LLM thật)
        inference_mode = getattr(request, "inference_mode", "llm")

        # Build mock memory view
        memory_view = self._build_mock_memory_view(request.use_memory, request.user_id)

        if status == "ok":
            # Nếu memory on, thêm MemoryTool step vào trace
            trace = _MOCK_TRAILS["ok"]
            if request.use_memory:
                trace = self._add_memory_tool_step(trace, request.user_id)
            return DemoResult(
                status="ok",
                text="Dựa trên yêu cầu của bạn, tôi đã tìm thấy các sản phẩm sau:",
                items=_MOCK_ITEMS[:2],
                trace=trace,
                usage=dict(trace.usage),
                error=None,
                memory=memory_view,
            )
        elif status == "ask_user":
            trace = _MOCK_TRAILS["ask_user"]
            if request.use_memory:
                trace = self._add_memory_tool_step(trace, request.user_id)
            return DemoResult(
                status="ask_user",
                text="Tôi cần thêm thông tin để gợi ý chính xác hơn.",
                items=[],
                trace=trace,
                usage=dict(trace.usage),
                error=None,
                memory=memory_view,
            )
        elif status == "no_result":
            trace = _MOCK_TRAILS["no_result"]
            if request.use_memory:
                trace = self._add_memory_tool_step(trace, request.user_id)
            return DemoResult(
                status="no_result",
                text="Không tìm thấy sản phẩm phù hợp với yêu cầu của bạn.",
                items=[],
                trace=trace,
                usage=dict(trace.usage),
                error=None,
                memory=memory_view,
            )
        else:  # tool_error
            trace = _MOCK_TRAILS["tool_error"]
            if request.use_memory:
                trace = self._add_memory_tool_step(trace, request.user_id)
            return DemoResult(
                status="tool_error",
                text="Có lỗi xảy ra khi xử lý yêu cầu. Vui lòng thử lại.",
                items=[],
                trace=trace,
                usage=dict(trace.usage),
                error="Lỗi tool: Item not found",
                memory=memory_view,
            )

    def _build_mock_memory_view(self, use_memory: bool, user_id: str | None) -> MemoryView:
        """Build mock MemoryView dựa trên user_id."""
        if not use_memory:
            return MemoryView(
                enabled=False,
                called=False,
                n_calls=0,
                before=None,
                after=None,
                agent_calls=[],
                consumed_by=[],
            )

        # Mock memory snapshot dựa trên user_id
        known = user_id is not None and user_id != "mock_cold_user"
        n_interactions = 0 if user_id == "mock_cold_user" else (3 if user_id == "mock_sparse_user" else 20)
        top_categories = ["Electronics"] if known else []
        price_range = {"min": 10.0, "max": 100.0} if known else None
        recent_items = ["Video_Games::B00EXAMPLE1"] if known else []

        snapshot = {
            "user_id": user_id or "unknown",
            "known": known,
            "n_interactions": n_interactions,
            "top_categories": top_categories,
            "price_range": price_range,
            "recent_items": recent_items,
        }

        return MemoryView(
            enabled=True,
            called=True,
            n_calls=1,
            before=snapshot,
            after=snapshot,
            agent_calls=[
                {
                    "tool": "MemoryTool",
                    "ok": True,
                    "error": None,
                    "args": {"user_id": user_id},
                    "data": snapshot,
                }
            ],
            consumed_by=[
                {
                    "memory_step_index": 0,
                    "consumer_step_index": 1,
                    "consumer_tool": "QueryTool",
                    "reference": "$0.top_categories",
                }
            ],
        )

    def _add_memory_tool_step(self, trace: DemoTrace, user_id: str | None) -> DemoTrace:
        """Thêm MemoryTool step vào mock trace."""
        memory_step = {
            "tool": "MemoryTool",
            "ok": True,
            "error": None,
            "latency_seconds": 0.05,
            "args": {"user_id": user_id},
            "output_summary": f"known={user_id != 'mock_cold_user'}",
        }
        return DemoTrace(
            plan=[{"tool": "MemoryTool", "args": {"user_id": user_id}}] + trace.plan,
            steps=[memory_step] + trace.steps,
            ask_user=trace.ask_user,
            reflections=trace.reflections,
            first_attempt_ok=trace.first_attempt_ok,
            truncated=trace.truncated,
            usage=trace.usage,
            inference=trace.inference,
        )
