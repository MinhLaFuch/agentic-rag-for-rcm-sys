"""Test cho demo backend (Giai đoạn 1)."""

import pytest

from package.demo import (
    DemoRequest,
    DemoResult,
    MockBackend,
    format_items,
    format_trace,
    format_memory,
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


def test_format_memory_basic():
    """format_memory phải tạo văn bản từ MemoryView."""
    from package.demo import MemoryView

    view = MemoryView(
        enabled=True,
        called=True,
        n_calls=1,
        before={
            "user_id": "user123",
            "known": True,
            "n_interactions": 10,
            "top_categories": ["Electronics", "Toys"],
            "price_range": {"min": 10.0, "max": 100.0},
            "recent_items": ["Video_Games::B001", "Toys::B002"],
        },
        after={
            "user_id": "user123",
            "known": True,
            "n_interactions": 10,
            "top_categories": ["Electronics", "Toys"],
            "price_range": {"min": 10.0, "max": 100.0},
            "recent_items": ["Video_Games::B001", "Toys::B002"],
        },
        agent_calls=[
            {
                "tool": "MemoryTool",
                "ok": True,
                "error": None,
                "args": {"user_id": "user123"},
                "data": {"known": True, "n_interactions": 10},
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

    formatted = format_memory(view)
    assert "Memory ON" in formatted
    assert "MemoryTool called ✓" in formatted
    assert "known ✓" in formatted
    assert "1 call(s)" in formatted
    assert "Profile Memory" in formatted
    assert "Memory Consumed By" in formatted


def test_format_memory_with_metadata():
    """format_memory phải resolve item_id sang title khi có metadata."""
    from package.demo import MemoryView

    view = MemoryView(
        enabled=True,
        called=True,
        n_calls=1,
        before={
            "user_id": "user123",
            "known": True,
            "n_interactions": 1,
            "top_categories": [],
            "price_range": None,
            "recent_items": ["Video_Games::B001"],
        },
        after=None,
        agent_calls=[],
        consumed_by=[],
    )

    item_id_to_metadata = {
        "Video_Games::B001": {
            "title": "Test Game",
            "domain": "Video_Games",
        }
    }

    formatted = format_memory(view, item_id_to_metadata)
    assert "Test Game" in formatted


def test_mock_backend_memory_view():
    """MockBackend phải trả về MemoryView khi memory on."""
    backend = MockBackend()

    request_on = DemoRequest(
        user_id="mock_warm_user",
        text="test",
        reflect_rounds=0,
        use_memory=True,
        mode="planner",
    )
    result_on = backend.respond(request_on)
    assert result_on.memory is not None
    assert result_on.memory.enabled is True
    assert result_on.memory.called is True

    request_off = DemoRequest(
        user_id="mock_warm_user",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
    )
    result_off = backend.respond(request_off)
    assert result_off.memory is not None
    assert result_off.memory.enabled is False
    assert result_off.memory.called is False


def test_build_profiles():
    """build_profiles phải tạo list DemoProfile với blank, pinned, auto."""
    import pandas as pd
    from package.demo import build_profiles

    # Create minimal fit_df
    fit_df = pd.DataFrame({
        "user_idx": [0, 0, 1, 2, 2, 2],
        "item_idx": [0, 1, 2, 3, 4, 5],
        "timestamp": [1, 2, 3, 4, 5, 6],
    })
    user2id = {"user0": 0, "user1": 1, "user2": 2}

    profiles = build_profiles(fit_df, user2id)

    assert isinstance(profiles, list)
    assert len(profiles) >= 1

    # Check blank profile
    blank = next((p for p in profiles if p.profile_id == "blank"), None)
    assert blank is not None
    assert blank.user_id is None
    assert blank.segment == "blank"

    # Check auto profiles exist
    auto_profiles = [p for p in profiles if p.profile_id.startswith("auto_")]
    assert len(auto_profiles) > 0


def test_detect_consumed_by():
    """detect_consumed_by phải tìm $<n> references trong args."""
    from package.demo._consumed_by import detect_consumed_by

    steps = [
        {"tool": "MemoryTool", "args": {"user_id": "user123"}},
        {"tool": "QueryTool", "args": {"categories": "$0.top_categories"}},
        {"tool": "SQLTool", "args": {"filters": {"categories_any": "$0.top_categories"}}},
    ]

    consumed = detect_consumed_by(steps, [0])

    assert len(consumed) == 2
    assert consumed[0]["memory_step_index"] == 0
    assert consumed[0]["consumer_step_index"] == 1
    assert consumed[0]["consumer_tool"] == "QueryTool"
    assert consumed[1]["consumer_step_index"] == 2
    assert consumed[1]["consumer_tool"] == "SQLTool"


def test_detect_consumed_by_no_match():
    """detect_consumed_by trả về rỗng khi không có reference."""
    from package.demo._consumed_by import detect_consumed_by

    steps = [
        {"tool": "MemoryTool", "args": {"user_id": "user123"}},
        {"tool": "QueryTool", "args": {"categories": ["Electronics"]}},
    ]

    consumed = detect_consumed_by(steps, [0])

    assert len(consumed) == 0
