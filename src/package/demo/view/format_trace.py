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
        status_icon = "✓" if ok else "✗"
        lines.append(f"{i}. {status_icon} **{tool}** ({latency:.3f}s)")
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
    return "\n".join(lines)
