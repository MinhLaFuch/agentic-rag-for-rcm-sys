"""Adapter từ nguồn dữ liệu (PlanExecutor hoặc Inference) sang DemoResult view model."""

from __future__ import annotations

from typing import Any

from package.agents.evaluation import extract_recommendations
from package.api._error import LLMProviderError
from ._limits import get_demo_limits
from ._view_model import DemoItem, DemoRequest, DemoResult, DemoTrace


def _format_status_from_plan_results(results: list[dict[str, Any]], ask_user: str | None) -> str:
    """Suy ra status từ kết quả PlanExecutor."""
    if ask_user:
        return "ask_user"
    rec_ids = extract_recommendations(results, k=10)
    if not rec_ids:
        return "no_result"
    return "ok"


def _generate_text_for_status(status: str, request: DemoRequest) -> str:
    """Hàm mẫu tất định tạo câu trả lời text cho UI (chỉ cho demo)."""
    if status == "ask_user":
        return "Tôi cần thêm thông tin để gợi ý chính xác hơn."
    if status == "no_result":
        return "Không tìm thấy sản phẩm phù hợp với yêu cầu của bạn."
    if status == "tool_error":
        return "Có lỗi xảy ra khi xử lý yêu cầu. Vui lòng thử lại."
    # status == "ok"
    if request.mode == "type1":
        return f"Dựa trên lịch sử mua hàng của bạn, đây là {len([])} sản phẩm tương tự."
    return f"Dựa trên yêu cầu của bạn, tôi đã tìm thấy các sản phẩm sau:"


def _extract_items_from_results(
    results: list[dict[str, Any]], item_id_to_metadata: dict[str, dict[str, Any]]
) -> list[DemoItem]:
    """Trích xuất DemoItem từ kết quả PlanExecutor."""
    limits = get_demo_limits()
    rec_ids = extract_recommendations(results, k=limits.max_items_display)
    items = []
    for item_id in rec_ids:
        meta = item_id_to_metadata.get(item_id, {})
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
    return items


def adapt_from_plan_executor(
    results: list[dict[str, Any]],
    executor_last_plan: list[dict[str, Any]],
    executor_last_question: str | None,
    executor_last_reflections: int,
    executor_last_first_attempt_ok: bool,
    executor_last_truncated: bool,
    executor_last_usage: dict[str, Any],
    request: DemoRequest,
    item_id_to_metadata: dict[str, dict[str, Any]],
) -> DemoResult:
    """Adapter từ kết quả PlanExecutor sang DemoResult."""
    limits = get_demo_limits()
    status = _format_status_from_plan_results(results, executor_last_question)
    text = _generate_text_for_status(status, request)
    items = _extract_items_from_results(results, item_id_to_metadata)

    trace = DemoTrace(
        plan=executor_last_plan,
        steps=[
            {
                "tool": r.get("tool"),
                "ok": r.get("ok"),
                "error": None if r.get("error") is None else str(r["error"])[:limits.max_error_length],
                "latency_seconds": r.get("latency_seconds"),
            }
            for r in results
        ],
        ask_user=executor_last_question,
        reflections=executor_last_reflections,
        first_attempt_ok=executor_last_first_attempt_ok,
        truncated=executor_last_truncated,
        usage=dict(executor_last_usage),
    )

    return DemoResult(
        status=status,
        text=text,
        items=items,
        trace=trace,
        usage=dict(executor_last_usage),
        error=None,
    )


def adapt_from_plan_executor_error(
    exc: Exception,
    request: DemoRequest,
) -> DemoResult:
    """Adapter khi PlanExecutor ném ngoại lệ."""
    limits = get_demo_limits()
    error_msg = f"{type(exc).__name__}: {exc}"[:limits.max_error_length]
    status = "tool_error"
    text = _generate_text_for_status(status, request)
    return DemoResult(
        status=status,
        text=text,
        items=[],
        trace=None,
        usage={},
        error=error_msg,
    )


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
