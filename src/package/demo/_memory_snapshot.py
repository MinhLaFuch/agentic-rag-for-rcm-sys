"""Helper để chụp snapshot memory thông qua MemoryTool.execute."""

from __future__ import annotations

from typing import Any


def take_memory_snapshot(memory_tool: Any, user_id: str | None) -> dict[str, Any] | None:
    """Chụp snapshot memory bằng cách gọi trực tiếp MemoryTool.execute.

    Args:
        memory_tool: Instance của MemoryTool (hoặc None nếu không có)
        user_id: User ID để snapshot (None cho blank profile)

    Returns:
        Dict kết quả từ MemoryTool.execute, hoặc None nếu không có tool hoặc user_id None
    """
    if memory_tool is None or user_id is None:
        return None
    try:
        return memory_tool.execute(user_id)
    except Exception:
        # Nếu lỗi (user không tồn tại, v.v.), trả về None
        return None
