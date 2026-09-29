"""
EDA functions cho interaction data (Phase 2, mục V/VI/XVIII).

Các hàm ở đây là pure function trên pandas DataFrame, KHÔNG tự tải dữ
liệu — vì vậy có thể unit test bằng dữ liệu synthetic (để verify logic
đúng), tách biệt hoàn toàn với việc dữ liệu thật có tải được hay không
(xem src/data/acquire.py — hiện đang BLOCKED do network).
"""

from __future__ import annotations

from collections import Counter

from ._dataclass import StreamingInteractionStats
from ..loader import iter_jsonl_gz

def compute_interaction_stats_streaming(path: str) -> "StreamingInteractionStats":
    """
    Đọc file review .jsonl.gz thật (schema: user_id, parent_asin, rating,
    timestamp, title, text, helpful_vote, verified_purchase) theo dòng,
    không load hết vào RAM. Phù hợp chạy trên máy người dùng với file
    lớn (ví dụ Video_Games ~4.6M review) mà không cần upload file lên chat.

    Sau khi chạy, in kết quả và paste lại cho Claude để cập nhật docs.
    """
    import gzip
    import json

    user_counts: Counter = Counter()
    item_ids: set = set()
    stats = StreamingInteractionStats()

    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)

            stats.num_interactions += 1
            user_counts[record["user_id"]] += 1
            item_ids.add(record["parent_asin"])

            ts = record.get("timestamp")
            if ts is not None:
                if stats.timestamp_min is None or ts < stats.timestamp_min:
                    stats.timestamp_min = ts
                if stats.timestamp_max is None or ts > stats.timestamp_max:
                    stats.timestamp_max = ts

            rating = record.get("rating")
            if isinstance(rating, (int, float)):
                stats.rating_sum += rating

    stats.num_users = len(user_counts)
    stats.num_items = len(item_ids)
    stats.interactions_per_user = dict(user_counts)
    return stats
