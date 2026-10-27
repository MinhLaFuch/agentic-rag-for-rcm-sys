"""Format MemoryView thành markdown cho UI."""

from __future__ import annotations

from .._limits import get_demo_limits
from ._dataclass import MemoryView


def format_memory(view: MemoryView, item_id_to_metadata: dict[str, dict[str, str]] | None = None) -> str:
    """Format MemoryView thành văn bản/markdown."""
    if view is None:
        return "No memory data"

    lines = []

    # Diagnostics line
    memory_status = "ON" if view.enabled else "OFF"
    called_status = "✓" if view.called else "✗"
    known_status = "✓" if (view.before and view.before.get("known")) else "✗" if view.before else "N/A"
    lines.append(f"**Memory {memory_status} · MemoryTool called {called_status} · known {known_status} · {view.n_calls} call(s)**")
    lines.append("")

    # Before/After snapshots
    if view.before is None and view.after is None:
        lines.append("No history data (blank profile)")
    else:
        lines.append("## Profile Memory")
        if view.before:
            lines.append(_format_snapshot("Before turn", view.before, item_id_to_metadata))
        if view.after:
            lines.append(_format_snapshot("After turn", view.after, item_id_to_metadata))

        # Check if changed
        if view.before and view.after and view.before == view.after:
            lines.append("")
            lines.append("*No change (MemoryTool is read-only)*")

    # Agent calls
    if view.agent_calls:
        lines.append("")
        lines.append("## MemoryTool Agent Calls")
        for i, call in enumerate(view.agent_calls, 1):
            tool = call.get("tool", "unknown")
            ok = call.get("ok", False)
            error = call.get("error")
            args = call.get("args", {})
            output = call.get("data", {})
            status_icon = "✓" if ok else "✗"
            lines.append(f"{i}. {status_icon} **{tool}**")
            if args:
                lines.append(f"   Args: {args}")
            if error:
                lines.append(f"   Error: {error}")
            if output:
                # Format output summary
                summary_parts = []
                if "known" in output:
                    summary_parts.append(f"known={output['known']}")
                if "n_interactions" in output:
                    summary_parts.append(f"n={output['n_interactions']}")
                if "top_categories" in output and output["top_categories"]:
                    summary_parts.append(f"cats={output['top_categories']}")
                if summary_parts:
                    lines.append(f"   Output: {', '.join(summary_parts)}")

    # Consumed by
    if view.consumed_by:
        lines.append("")
        lines.append("## Memory Consumed By")
        for ref in view.consumed_by:
            mem_idx = ref.get("memory_step_index")
            cons_idx = ref.get("consumer_step_index")
            cons_tool = ref.get("consumer_tool", "unknown")
            reference = ref.get("reference", "")
            lines.append(f"- Step {cons_idx} ({cons_tool}) ← step {mem_idx} via {reference}")

    return "\n".join(lines)


def _format_snapshot(label: str, snapshot: dict[str, any], item_id_to_metadata: dict[str, dict[str, str]] | None = None) -> str:
    """Format một snapshot memory."""
    lines = [f"### {label}"]
    lines.append(f"- User ID: {snapshot.get('user_id', 'N/A')}")
    lines.append(f"- Known: {snapshot.get('known', False)}")
    lines.append(f"- Interactions: {snapshot.get('n_interactions', 0)}")

    top_cats = snapshot.get("top_categories", [])
    if top_cats:
        lines.append(f"- Top categories: {', '.join(top_cats)}")

    price_range = snapshot.get("price_range")
    if price_range:
        lines.append(f"- Price range: ${price_range.get('min', 0):.2f} - ${price_range.get('max', 0):.2f}")

    recent_items = snapshot.get("recent_items", [])
    if recent_items:
        max_display = get_demo_limits().max_recent_items_display
        lines.append(f"- Recent items ({len(recent_items)}):")
        for item_id in recent_items[:max_display]:
            if item_id_to_metadata and item_id in item_id_to_metadata:
                meta = item_id_to_metadata[item_id]
                title = meta.get("title", item_id)
                lines.append(f"  - {title} ({item_id})")
            else:
                lines.append(f"  - {item_id}")

    return "\n".join(lines)
