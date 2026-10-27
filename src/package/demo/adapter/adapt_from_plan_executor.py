"""Adapter từ kết quả PlanExecutor sang DemoResult view model."""

from __future__ import annotations

from typing import Any

from package.agents import extract_recommendations
from ..view import DemoItem, DemoRequest, DemoResult, DemoTrace
from ._helper import _generate_text_for_status
from .._limits import get_demo_limits


def _format_status_from_plan_results(results: list[dict[str, Any]], ask_user: str | None) -> str:
    """Suy ra status từ kết quả PlanExecutor."""
    if ask_user:
        return "ask_user"
    rec_ids = extract_recommendations(results, k=10)
    if not rec_ids:
        return "no_result"
    return "ok"


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
        inference=None,
    )

    return DemoResult(
        status=status,
        text=text,
        items=items,
        trace=trace,
        usage=dict(executor_last_usage),
        error=None,
    )
