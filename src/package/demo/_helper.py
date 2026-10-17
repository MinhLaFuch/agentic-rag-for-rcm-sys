"""Helper nội bộ của demo: văn bản trạng thái dùng chung cho các adapter."""

from __future__ import annotations

from ._dataclass import DemoRequest


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
