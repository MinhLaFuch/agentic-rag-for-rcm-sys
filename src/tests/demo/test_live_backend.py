"""Test cho LiveBackend với ScriptedLLM (không cần LLM thật)."""

import json

import pytest

from package.agents import PlanExecutor
from package.api.base import LLMProvider
from package.api._dataclass import LLMResponse
from package.demo import DemoRequest, adapt_from_plan_executor, adapt_from_plan_executor_error
from package.tools import QueryTool, SQLTool
from tests.tools_helpers import VG_A


class ScriptedLLM(LLMProvider):
    """LLM giả trả kết quả đã định sẵn."""
    provider_name = "scripted"

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[list] = []

    def complete(self, messages, *, temperature=0.0, max_tokens=512, response_format_json=False):
        self.calls.append(list(messages))
        return LLMResponse(
            text=self.replies.pop(0),
            prompt_tokens=10,
            completion_tokens=5,
            latency_seconds=0.1,
            provider_name="scripted",
            model_name="scripted-0",
        )


def plan(*steps, ask_user=None) -> str:
    """Tạo JSON plan."""
    return json.dumps({"steps": list(steps), "ask_user": ask_user})


def test_adapt_from_plan_executor_ok_status(corpus):
    """Adapter phải chuyển kết quả PlanExecutor thành DemoResult với status='ok'."""
    steps = [{"tool": "QueryTool", "args": {"item_ids": [VG_A]}}]
    executor = PlanExecutor(ScriptedLLM(plan(*steps)), [QueryTool(corpus)])
    results = executor.run(f"tell me about {VG_A}")

    request = DemoRequest(
        user_id="user123",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
    )

    item_id_to_metadata = {
        VG_A: {
            "domain": "Video_Games",
            "title": "Test Game",
            "store": "Amazon",
            "price": 49.99,
            "average_rating": 4.5,
            "rating_number": 100,
            "main_category": "Electronics",
        }
    }

    result = adapt_from_plan_executor(
        results=results,
        executor_last_plan=executor.last_plan,
        executor_last_question=executor.last_question,
        executor_last_reflections=executor.last_reflections,
        executor_last_first_attempt_ok=executor.last_first_attempt_ok,
        executor_last_truncated=executor.last_truncated,
        executor_last_usage=executor.last_usage,
        request=request,
        item_id_to_metadata=item_id_to_metadata,
    )

    assert result.status == "ok"
    assert result.text != ""
    assert isinstance(result.items, list)
    assert result.trace is not None
    assert result.trace.steps[0]["ok"] is True
    assert result.error is None


def test_adapt_from_plan_executor_ask_user_status(corpus):
    """Adapter phải chuyển kết quả PlanExecutor với ask_user thành status='ask_user'."""
    executor = PlanExecutor(ScriptedLLM(plan(ask_user="Which category?")), [SQLTool(corpus)])
    results = executor.run("recommend something")

    request = DemoRequest(
        user_id="user123",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
    )

    result = adapt_from_plan_executor(
        results=results,
        executor_last_plan=executor.last_plan,
        executor_last_question=executor.last_question,
        executor_last_reflections=executor.last_reflections,
        executor_last_first_attempt_ok=executor.last_first_attempt_ok,
        executor_last_truncated=executor.last_truncated,
        executor_last_usage=executor.last_usage,
        request=request,
        item_id_to_metadata={},
    )

    assert result.status == "ask_user"
    assert result.trace is not None
    assert result.trace.ask_user == "Which category?"


def test_adapt_from_plan_executor_no_result_status(corpus):
    """Adapter phải chuyển kết quả PlanExecutor không có item thành status='no_result'."""
    steps = [{"tool": "SQLTool", "args": {"limit": 0}}]
    # Cung cấp 2 replies để tránh lỗi pop từ empty list (nếu có reflect)
    executor = PlanExecutor(ScriptedLLM(plan(*steps), plan(*steps)), [SQLTool(corpus)], reflect_rounds=0)
    results = executor.run("list items")

    request = DemoRequest(
        user_id="user123",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
    )

    result = adapt_from_plan_executor(
        results=results,
        executor_last_plan=executor.last_plan,
        executor_last_question=executor.last_question,
        executor_last_reflections=executor.last_reflections,
        executor_last_first_attempt_ok=executor.last_first_attempt_ok,
        executor_last_truncated=executor.last_truncated,
        executor_last_usage=executor.last_usage,
        request=request,
        item_id_to_metadata={},
    )

    assert result.status == "no_result"
    assert len(result.items) == 0


def test_adapt_from_plan_executor_error():
    """Adapter phải chuyển exception thành DemoResult với status='tool_error'."""
    request = DemoRequest(
        user_id="user123",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
    )

    result = adapt_from_plan_executor_error(ValueError("Invalid plan"), request)

    assert result.status == "tool_error"
    assert result.error is not None
    assert "ValueError" in result.error
    assert result.items == []
    assert result.trace is None


def test_adapter_cuts_error_message():
    """Adapter phải cắt gọn thông báo lỗi (MAX_ERROR_LENGTH)."""
    long_error = "x" * 500
    request = DemoRequest(
        user_id="user123",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
    )

    result = adapt_from_plan_executor_error(RuntimeError(long_error), request)

    assert len(result.error) <= 300  # MAX_ERROR_LENGTH


def test_adapter_no_api_key_in_result(corpus):
    """API key không được xuất hiện trong DemoResult/trace."""
    steps = [{"tool": "QueryTool", "args": {"item_ids": [VG_A]}}]
    executor = PlanExecutor(ScriptedLLM(plan(*steps)), [QueryTool(corpus)])
    results = executor.run(f"tell me about {VG_A}")

    request = DemoRequest(
        user_id="user123",
        text="test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
    )

    result = adapt_from_plan_executor(
        results=results,
        executor_last_plan=executor.last_plan,
        executor_last_question=executor.last_question,
        executor_last_reflections=executor.last_reflections,
        executor_last_first_attempt_ok=executor.last_first_attempt_ok,
        executor_last_truncated=executor.last_truncated,
        executor_last_usage=executor.last_usage,
        request=request,
        item_id_to_metadata={VG_A: {"domain": "Video_Games", "title": "Test"}},
    )

    # Chuyển thành JSON string để kiểm tra
    result_str = json.dumps({
        "status": result.status,
        "text": result.text,
        "items": [i.__dict__ for i in result.items],
        "trace": result.trace.__dict__ if result.trace else None,
        "usage": result.usage,
        "error": result.error,
    })

    # Kiểm tra không có từ khóa liên quan API key
    assert "api_key" not in result_str.lower()
    assert "secret" not in result_str.lower()
    assert "token" not in result_str.lower() or "tokens" in result_str  # cho phép "tokens" (usage)


def test_live_backend_get_sample_users(corpus):
    """LiveBackend.get_sample_users phải trả dict với 3 segment."""
    from package.demo import LiveBackend
    from package.data.mapping import load_mappings
    from package.data.split import load_splits
    from package.config import get_data_paths

    # Dùng tag/default để test nhanh
    data_paths = get_data_paths()
    train, _, _ = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    user2id, _ = load_mappings(data_paths.mapped_dir)

    backend = LiveBackend()
    backend._fit_df = train
    backend._user_id_to_internal_id = user2id

    sample_dict = backend.get_sample_users(n_per_segment=2, sparse_max=5)

    assert isinstance(sample_dict, dict)
    assert set(sample_dict.keys()) == {"cold", "sparse", "warm"}
    # Số lượng user mỗi segment có thể ít hơn n_per_segment nếu không đủ user
    for segment, users in sample_dict.items():
        assert isinstance(users, list)
        assert len(users) <= 2
