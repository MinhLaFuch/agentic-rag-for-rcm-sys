"""Adapter từ Inference.Answer sang DemoResult (chỗ giữ chỗ)."""

from __future__ import annotations

from typing import Any

from ._dataclass import DemoResult


def adapt_from_inference(answer: Any) -> DemoResult:
    """Adapter từ Inference.Answer sang DemoResult (chỗ giữ chỗ)."""
    # Khi package.inference có compose_answer, sẽ ánh xạ:
    # answer.status -> status
    # answer.text -> text
    # answer.items -> items (có metadata sẵn)
    # answer.grounded -> có thể thêm vào trace
    # answer.composer -> có thể thêm vào trace
    # answer.fallback_reason -> error nếu có
    # answer.usage -> usage
    # Hiện tại: giữ chỗ, sẽ được implement khi Inference hoàn thiện
    raise NotImplementedError("Inference adapter chưa được implement - chờ tầng Inference hoàn thiện")
