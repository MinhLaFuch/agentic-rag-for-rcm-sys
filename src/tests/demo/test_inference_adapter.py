"""Test cho adapter Inference (chỗ giữ chỗ cho tương lai)."""

import pytest

from dataclasses import dataclass

from package.demo import adapt_from_inference


# Định nghĩa Answer giả (khi package.inference chưa có)
@dataclass
class FakeAnswer:
    """Answer giả cho test."""
    status: str
    text: str
    items: list[dict]
    grounded: bool
    composer: str
    fallback_reason: str | None
    usage: dict


def test_inference_adapter_not_implemented():
    """Adapter Inference phải raise NotImplementedError (chỗ giữ chỗ)."""
    fake_answer = FakeAnswer(
        status="ok",
        text="Test response",
        items=[{"item_id": "Video_Games::B001", "title": "Test"}],
        grounded=True,
        composer="llm",
        fallback_reason=None,
        usage={"tokens": 100},
    )

    with pytest.raises(NotImplementedError, match="Inference adapter chưa được implement"):
        adapt_from_inference(fake_answer)
