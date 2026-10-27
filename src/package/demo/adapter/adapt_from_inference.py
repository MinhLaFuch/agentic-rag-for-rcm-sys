"""Adapter từ Inference.Answer sang DemoResult."""

from __future__ import annotations

from typing import Any

from package.inference import Answer
from ..view import DemoItem, DemoRequest, DemoResult, DemoTrace
from .._limits import get_demo_limits


def adapt_from_inference(
    answer: Answer,
    *,
    request: DemoRequest,
    item_id_to_metadata: dict[str, dict[str, Any]],
    trace: DemoTrace | None = None,
) -> DemoResult:
    """Adapter từ Inference.Answer sang DemoResult.

    Args:
        answer: Answer từ compose_answer
        request: DemoRequest gốc
        item_id_to_metadata: Mapping từ item_id sang metadata (để bổ sung nếu thiếu)
        trace: DemoTrace từ planner/type1 (có thể None cho type1), sẽ được cập nhật với thông tin inference

    Returns:
        DemoResult cho UI
    """
    limits = get_demo_limits()

    # Chuyển items từ Answer sang DemoItem
    items = []
    for item in answer.items:
        item_id = item.get("item_id", "")
        # Ưu tiên metadata từ answer.items (đã đầy đủ), bổ sung từ item_id_to_metadata nếu thiếu
        meta = dict(item)
        for key, value in item_id_to_metadata.get(item_id, {}).items():
            if key not in meta or meta[key] is None:
                meta[key] = value
        items.append(
            DemoItem(
                item_id=item_id,
                domain=meta.get("domain", ""),
                title=meta.get("title", ""),
                store=meta.get("store"),
                price=meta.get("price"),
                average_rating=meta.get("average_rating"),
                rating_number=meta.get("rating_number"),
                main_category=meta.get("main_category"),
            )
        )

    # Error chỉ khi status == "tool_error"
    error = None
    if answer.status == "tool_error" and answer.reason:
        error = answer.reason[:limits.max_error_length]

    # Cập nhật trace với thông tin inference
    inference_info = {
        "composer": answer.composer,
        "grounded": answer.grounded,
        "fallback_reason": answer.fallback_reason,
        "reason": answer.reason,
        "usage": dict(answer.usage),
    }
    if trace is not None:
        trace.inference = inference_info
    else:
        # Tạo trace mới chỉ có thông tin inference (cho type1)
        trace = DemoTrace(
            plan=[],
            steps=[],
            ask_user=None,
            reflections=0,
            first_attempt_ok=True,
            truncated=False,
            usage={},
            inference=inference_info,
        )

    return DemoResult(
        status=answer.status,
        text=answer.text,
        items=items,
        trace=trace,
        usage=dict(answer.usage),
        error=error,
    )
