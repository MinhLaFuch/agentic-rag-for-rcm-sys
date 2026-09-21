"""Dựng prompt rerank từ lịch sử user + candidates."""


def build_prompt(user_history_titles: list[str], candidates: list[dict]) -> str:
    history_str = "\n".join(f"- {t}" for t in user_history_titles) or "(chưa có lịch sử)"
    candidates_str = "\n".join(
        f"{c['item_idx']}. {c['title']} (category: {c['category']}, backend_score: {c['score']:.3f})"
        for c in candidates
    )
    return f"""Bạn là trợ lý gợi ý mua sắm. Dưới đây là lịch sử mua/xem gần đây của user:
{history_str}

Đây là danh sách candidate do hệ thống gợi ý nền đề xuất (đã sắp theo backend_score):
{candidates_str}

Nhiệm vụ: sắp xếp lại danh sách trên theo mức độ phù hợp với user (có thể giữ nguyên thứ tự
nếu thấy backend đã hợp lý), và giải thích ngắn gọn (1 câu) lý do cho mỗi item.

Trả lời CHỈ bằng JSON, đúng format sau, không thêm chữ nào khác:
[{{"item_idx": <int>, "rank": <int, 1 là cao nhất>, "reason": "<1 câu>"}}]"""
