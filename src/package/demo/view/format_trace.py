"""Format vết thực thi (DemoTrace) thành markdown cho UI."""

from __future__ import annotations

from ._dataclass import DemoTrace


def format_trace(trace: DemoTrace) -> str:
    """Format vết thực thi thành văn bản/markdown."""
    lines = []
    lines.append(f"## Plan JSON ({len(trace.plan)} steps)")
    lines.append("```json")
    lines.append(str(trace.plan)[:500])  # cắt gọn nếu quá dài
    lines.append("```")
    lines.append("")
    lines.append("## Thực thi từng step")
    for i, step in enumerate(trace.steps, 1):
        tool = step.get("tool", "unknown")
        ok = step.get("ok", False)
        error = step.get("error")
        latency = step.get("latency_seconds", 0)
        args = step.get("args")
        output_summary = step.get("output_summary")
        status_icon = "✓" if ok else "✗"
        lines.append(f"{i}. {status_icon} **{tool}** ({latency:.3f}s)")
        if args:
            lines.append(f"   Args: {args}")
        if output_summary:
            lines.append(f"   Output: {output_summary}")
        if error:
            lines.append(f"   Lỗi: {error}")
    lines.append("")
    lines.append("## Thống kê")
    lines.append(f"- Số lần reflect: {trace.reflections}")
    lines.append(f"- Lần đầu thành công: {trace.first_attempt_ok}")
    lines.append(f"- Plan bị cắt gọn: {trace.truncated}")
    lines.append(f"- Lần gọi LLM: {trace.usage.get('attempts', 0)}")
    lines.append(f"- Tokens: {trace.usage.get('prompt_tokens', 0)} + {trace.usage.get('completion_tokens', 0)}")
    lines.append(f"- Tổng độ trễ LLM: {trace.usage.get('latency_seconds', 0):.2f}s")
    if trace.ask_user:
        lines.append(f"- Câu hỏi lại: {trace.ask_user}")
    if trace.inference:
        lines.append("")
        lines.append("## Inference (tạo câu trả lời)")
        lines.append(f"- Composer: {trace.inference.get('composer', 'unknown')}")
        lines.append(f"- Grounded: {trace.inference.get('grounded', True)}")
        if trace.inference.get('fallback_reason'):
            lines.append(f"- Fallback reason: {trace.inference['fallback_reason']}")
        if trace.inference.get('reason'):
            lines.append(f"- Reason: {trace.inference['reason']}")
        inf_usage = trace.inference.get('usage', {})
        lines.append(f"- Lần gọi LLM: {inf_usage.get('attempts', 0)}")
        lines.append(f"- Tokens: {inf_usage.get('prompt_tokens', 0)} + {inf_usage.get('completion_tokens', 0)}")
        lines.append(f"- Độ trễ: {inf_usage.get('latency_seconds', 0):.2f}s")
    return "\n".join(lines)
