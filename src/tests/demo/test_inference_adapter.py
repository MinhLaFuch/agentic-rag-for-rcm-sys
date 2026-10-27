"""Test cho adapter từ Inference.Answer sang DemoResult."""

import pytest

from package.demo import adapt_from_inference, DemoRequest, DemoTrace
from package.inference import Answer


class FakeLLMResponse:
    """LLM response giả cho test."""
    def __init__(self, text: str, prompt_tokens: int = 100, completion_tokens: int = 50, latency_seconds: float = 0.5):
        self.text = text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.latency_seconds = latency_seconds


def test_adapt_from_inference_ok():
    """Test chuyển Answer status ok sang DemoResult."""
    answer = Answer(
        status="ok",
        text="Dựa trên yêu cầu của bạn, tôi đã tìm thấy các sản phẩm sau:",
        items=[
            {
                "item_id": "Video_Games::B001",
                "title": "Test Game",
                "domain": "Video_Games",
                "price": 49.99,
                "average_rating": 4.5,
                "rating_number": 100,
                "store": "Amazon",
                "main_category": "Electronics",
            }
        ],
        grounded=True,
        composer="llm",
        fallback_reason=None,
        usage={"attempts": 1, "prompt_tokens": 100, "completion_tokens": 50, "latency_seconds": 0.5},
        reason=None,
    )

    request = DemoRequest(
        user_id=None,
        text="Recommend games",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
        inference_mode="llm",
    )

    item_id_to_metadata = {}
    trace = DemoTrace(
        plan=[],
        steps=[],
        ask_user=None,
        reflections=0,
        first_attempt_ok=True,
        truncated=False,
        usage={},
        inference=None,
    )

    result = adapt_from_inference(answer, request=request, item_id_to_metadata=item_id_to_metadata, trace=trace)

    assert result.status == "ok"
    assert result.text == answer.text
    assert len(result.items) == 1
    assert result.items[0].item_id == "Video_Games::B001"
    assert result.error is None
    assert result.trace is not None
    assert result.trace.inference is not None
    assert result.trace.inference["composer"] == "llm"
    assert result.trace.inference["grounded"] is True
    assert result.trace.inference["fallback_reason"] is None


def test_adapt_from_inference_ask_user():
    """Test chuyển Answer status ask_user sang DemoResult."""
    answer = Answer(
        status="ask_user",
        text="Bạn muốn tìm sản phẩm thuộc danh mục nào?",
        items=[],
        grounded=True,
        composer="template",
        fallback_reason=None,
        usage={"attempts": 0},
        reason="ask_user",
    )

    request = DemoRequest(
        user_id=None,
        text="I want something",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
        inference_mode="template",
    )

    result = adapt_from_inference(answer, request=request, item_id_to_metadata={}, trace=None)

    assert result.status == "ask_user"
    assert result.text == "Bạn muốn tìm sản phẩm thuộc danh mục nào?"
    assert len(result.items) == 0
    assert result.error is None
    assert result.trace is not None
    assert result.trace.inference is not None
    assert result.trace.inference["composer"] == "template"


def test_adapt_from_inference_no_result():
    """Test chuyển Answer status no_result sang DemoResult."""
    answer = Answer(
        status="no_result",
        text="Không tìm thấy sản phẩm phù hợp với yêu cầu của bạn.",
        items=[],
        grounded=True,
        composer="template",
        fallback_reason=None,
        usage={"attempts": 0},
        reason="no_result",
    )

    request = DemoRequest(
        user_id=None,
        text="Nonexistent product",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
        inference_mode="template",
    )

    result = adapt_from_inference(answer, request=request, item_id_to_metadata={}, trace=None)

    assert result.status == "no_result"
    assert result.text == "Không tìm thấy sản phẩm phù hợp với yêu cầu của bạn."
    assert len(result.items) == 0
    assert result.error is None


def test_adapt_from_inference_tool_error():
    """Test chuyển Answer status tool_error sang DemoResult."""
    answer = Answer(
        status="tool_error",
        text="Có lỗi xảy ra khi xử lý yêu cầu. Vui lòng thử lại.",
        items=[],
        grounded=True,
        composer="template",
        fallback_reason=None,
        usage={"attempts": 0},
        reason="tool_error: QueryTool failed",
    )

    request = DemoRequest(
        user_id=None,
        text="Invalid request",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
        inference_mode="template",
    )

    result = adapt_from_inference(answer, request=request, item_id_to_metadata={}, trace=None)

    assert result.status == "tool_error"
    assert result.text == "Có lỗi xảy ra khi xử lý yêu cầu. Vui lòng thử lại."
    assert len(result.items) == 0
    assert result.error is not None
    assert "tool_error" in result.error
    assert result.trace.inference["reason"] == "tool_error: QueryTool failed"


def test_adapt_from_inference_fallback():
    """Test chuyển Answer với fallback_reason (LLM lỗi về template)."""
    answer = Answer(
        status="ok",
        text="Dựa trên yêu cầu của bạn, tôi đã tìm thấy các sản phẩm sau:",  # template text
        items=[{"item_id": "Video_Games::B001", "title": "Test"}],
        grounded=True,
        composer="template",  # fallback về template
        fallback_reason="invalid_json: LLM returned malformed JSON",
        usage={"attempts": 2, "prompt_tokens": 200, "completion_tokens": 100, "latency_seconds": 1.0},
        reason="fallback",
    )

    request = DemoRequest(
        user_id=None,
        text="Recommend games",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
        inference_mode="llm",
    )

    result = adapt_from_inference(answer, request=request, item_id_to_metadata={}, trace=None)

    assert result.status == "ok"
    assert result.trace.inference["composer"] == "template"
    assert result.trace.inference["fallback_reason"] == "invalid_json: LLM returned malformed JSON"
    assert result.trace.inference["usage"]["attempts"] == 2


def test_adapt_from_inference_merge_metadata():
    """Test merge metadata từ answer.items và item_id_to_metadata."""
    answer = Answer(
        status="ok",
        text="Test",
        items=[
            {
                "item_id": "Video_Games::B001",
                "title": "Game Title",
                "domain": "Video_Games",
                # thiếu các field khác
            }
        ],
        grounded=True,
        composer="llm",
        fallback_reason=None,
        usage={},
    )

    request = DemoRequest(
        user_id=None,
        text="Test",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
        inference_mode="llm",
    )

    item_id_to_metadata = {
        "Video_Games::B001": {
            "price": 49.99,
            "average_rating": 4.5,
            "rating_number": 100,
            "store": "Amazon",
            "main_category": "Electronics",
        }
    }

    result = adapt_from_inference(answer, request=request, item_id_to_metadata=item_id_to_metadata, trace=None)

    assert len(result.items) == 1
    assert result.items[0].item_id == "Video_Games::B001"
    assert result.items[0].title == "Game Title"  # từ answer.items
    assert result.items[0].price == 49.99  # từ item_id_to_metadata
    assert result.items[0].average_rating == 4.5  # từ item_id_to_metadata
    assert result.items[0].store == "Amazon"  # từ item_id_to_metadata
