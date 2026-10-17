"""Badge hiển thị cho status của DemoResult."""

from __future__ import annotations


def status_badge(status: str) -> str:
    """Trả về badge hiển thị cho status."""
    badges = {
        "ok": "✅ Thành công",
        "ask_user": "❓ Cần thông tin thêm",
        "no_result": "⚠️ Không có kết quả",
        "tool_error": "❌ Lỗi hệ thống",
    }
    return badges.get(status, f"❓ {status}")
