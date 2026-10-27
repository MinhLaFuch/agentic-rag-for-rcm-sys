"""Helper để detect step nào đã dùng output của MemoryTool ($<n>)."""

from __future__ import annotations

import re
from typing import Any


def detect_consumed_by(steps: list[dict[str, Any]], memory_step_indices: list[int]) -> list[dict[str, Any]]:
    """Detect step nào đã dùng output của MemoryTool thông qua $<n> reference.

    Args:
        steps: Danh sách step từ executor results
        memory_step_indices: Indices của các step là MemoryTool (0-based)

    Returns:
        List of dict với keys: memory_step_index, consumer_step_index, consumer_tool, reference
    """
    consumed: list[dict[str, Any]] = []

    for mem_idx in memory_step_indices:
        # Pattern để tìm $<n> trong args
        pattern = re.compile(rf"\${mem_idx}\b")
        for i, step in enumerate(steps):
            if i == mem_idx:
                continue  # Bỏ qua chính MemoryTool step
            args = step.get("args", {})
            if isinstance(args, dict):
                # Tìm trong values của dict args
                for key, value in args.items():
                    value_str = str(value)
                    if pattern.search(value_str):
                        consumed.append(
                            {
                                "memory_step_index": mem_idx,
                                "consumer_step_index": i,
                                "consumer_tool": step.get("tool", "unknown"),
                                "reference": f"${mem_idx}.{key}" if key else f"${mem_idx}",
                            }
                        )
                        break  # Chỉ cần tìm thấy một reference trong step này

    return consumed
