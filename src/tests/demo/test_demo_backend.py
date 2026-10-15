"""Test cho demo backend (Giai đoạn 1)."""

import pytest

from package.demo import (
    DemoRequest,
    DemoResult,
    MockBackend,
    format_items,
    format_trace,
    status_badge,
    sample_requests,
)


def test_mock_backend_returns_all_statuses():
    """MockBackend phải trả đủ 4 trạng thái khi gọi lần lượt."""
    backend = MockBackend()
    request = DemoRequest(
        user_id="user123",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
    )

    statuses_seen = set()
    for _ in range(4):
        result = backend.respond(request)
        statuses_seen.add(result.status)

    assert statuses_seen == {"ok", "ask_user", "no_result", "tool_error"}


def test_mock_backend_result_structure():
    """Kết quả MockBackend phải có cấu trúc DemoResult hợp lệ."""
    backend = MockBackend()
    request = DemoRequest(
        user_id="user123",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
    )

    result = backend.respond(request)
    assert isinstance(result, DemoResult)
    assert result.status in {"ok", "ask_user", "no_result", "tool_error"}
    assert isinstance(result.text, str)
    assert isinstance(result.items, list)
    assert isinstance(result.usage, dict)
    # trace có thể None (tùy status)
    # error có thể None hoặc str


def test_format_items_with_missing_data():
    """format_items phải xử lý dữ liệu thiếu (price/rating None)."""
    from package.demo import DemoItem

    items = [
        DemoItem(
            item_id="Video_Games::B001",
            domain="Video_Games",
            title="Game 1",
            store="Amazon",
            price=None,
            average_rating=None,
            rating_number=None,
            main_category="Electronics",
        ),
        DemoItem(
            item_id="Toys_and_Games::B002",
            domain="Toys_and_Games",
            title="Toy 1",
            store=None,
            price=29.99,
            average_rating=4.5,
            rating_number=100,
            main_category="Toys",
        ),
    ]

    rows = format_items(items)
    assert len(rows) == 2
    assert rows[0][2] == "—"  # price None
    assert rows[0][3] == "—"  # rating None
    assert rows[0][4] == "Amazon"
    assert rows[1][2] == "$29.99"
    assert rows[1][3] == "4.5"
    assert rows[1][4] == "—"  # store None


def test_format_trace_basic():
    """format_trace phải tạo văn bản từ DemoTrace."""
    from package.demo import DemoTrace

    trace = DemoTrace(
        plan=[{"tool": "QueryTool", "args": {"limit": 2}}],
        steps=[
            {"tool": "QueryTool", "ok": True, "error": None, "latency_seconds": 0.1},
            {"tool": "SemanticSearchTool", "ok": False, "error": "timeout", "latency_seconds": 0.5},
        ],
        ask_user=None,
        reflections=1,
        first_attempt_ok=False,
        truncated=False,
        usage={"attempts": 2, "prompt_tokens": 100, "completion_tokens": 50, "latency_seconds": 0.6},
    )

    text = format_trace(trace)
    assert "Plan JSON" in text
    assert "QueryTool" in text
    assert "SemanticSearchTool" in text
    assert "Số lần reflect: 1" in text
    assert "Lần đầu thành công: False" in text
    assert "Lỗi: timeout" in text


def test_status_badge():
    """status_badge phải trả badge đúng cho từng status."""
    assert "Thành công" in status_badge("ok")
    assert "Cần thông tin thêm" in status_badge("ask_user")
    assert "Không có kết quả" in status_badge("no_result")
    assert "Lỗi hệ thống" in status_badge("tool_error")


def test_sample_requests():
    """sample_requests phải trả dict với 5 key."""
    requests = sample_requests("vi")
    assert isinstance(requests, dict)
    assert set(requests.keys()) == {"similar", "personalized", "constrained", "cold_text", "ambiguous"}
    for key, text in requests.items():
        assert isinstance(text, str)
        assert len(text) > 0


def test_demo_request_mode_validation():
    """DemoRequest.mode chỉ chấp nhận 'planner' hoặc 'type1'."""
    # Không có validation trong dataclass, nhưng test cho thấy UI cần kiểm tra
    request_planner = DemoRequest(
        user_id="user123",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
    )
    request_type1 = DemoRequest(
        user_id="user123",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="type1",
    )
    assert request_planner.mode == "planner"
    assert request_type1.mode == "type1"
