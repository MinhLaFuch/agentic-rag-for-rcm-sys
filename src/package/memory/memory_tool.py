"""
MemoryTool (bản "nhẹ" — phương án A).

Amazon Reviews 2023 không có hội thoại multi-turn, nên không có gì để LLM
trích preference ra (kiểu InteRecAgent's UserProfileMemory). Bản này chỉ
retrieve: tổng hợp thống kê từ chính interaction history + ItemCorpus đã có
sẵn (category hay mua, khoảng giá) — không write/update/forget, vì không có
nguồn hội thoại nào để ghi vào.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..data.leakage import check_profile_snapshot
from ..tools import get_tool_limits
from ..tools.base import Tool, validate_int
from ..tools.corpus import ItemCorpus

MEMORY_DEFAULT_TOP_N_CATEGORIES = get_tool_limits().memory_default_top_n_categories
MEMORY_RECENT_ITEMS = get_tool_limits().memory_recent_items


class MemoryTool(Tool):
    name = "MemoryTool"
    description = (
        "Retrieve a lightweight summary of a user's past purchase pattern "
        "(top categories, price range, recent items) derived from their interaction history. "
        "Read-only — no write/update, since there is no dialogue to extract "
        "preferences from in this dataset."
    )
    input_schema = {
        "user_id": "str",
        "top_n_categories": f"int (default {MEMORY_DEFAULT_TOP_N_CATEGORIES})",
    }
    output_schema = {
        "user_id": "str", "known": "bool  -- False = no history (unknown user or 0 interactions: cold start)", "n_interactions": "int",
        "top_categories": "list[str]  -- e.g. use as filters.categories_any via \"$1.top_categories\"",
        "price_range": "{min, max} | None  -- e.g. \"$1.price_range.max\" for filters.price_max",
        "recent_items": "list[str]  -- namespaced item ids, most recent first; use as ItemCFTool.items via \"$1.recent_items\"",
    }

    def __init__(
        self,
        interactions: pd.DataFrame,
        user2id: dict[str, int],
        item2id: dict[str, int],
        corpus: ItemCorpus,
        logger=None,
        as_of_timestamp: int | None = None,  # nếu có: chỉ dùng interactions với timestamp <= mốc này
    ) -> None:
        super().__init__(logger)
        if as_of_timestamp is not None:
            if "timestamp" not in interactions.columns:
                raise ValueError("as_of_timestamp needs a `timestamp` column in interactions")
            check_profile_snapshot(as_of_timestamp, interactions)  # profile tại t chỉ được dùng dữ liệu <= t (mục VI)
        self.interactions = interactions
        self.user2id = user2id
        self.id2item = {v: k for k, v in item2id.items()}
        self.corpus = corpus
        self.as_of_timestamp = as_of_timestamp

    def execute(self, user_id: str, top_n_categories: int = MEMORY_DEFAULT_TOP_N_CATEGORIES) -> dict[str, Any]:
        top_n_categories = validate_int(top_n_categories, "top_n_categories")
        uidx = self.user2id.get(user_id)  # user lạ hoặc 0 tương tác: known=False (cold-start, như RecoModelTool), không ném lỗi

        # Apply as_of_timestamp filter if set (leakage prevention)
        user_interactions = self.interactions
        if self.as_of_timestamp is not None and "timestamp" in user_interactions.columns:
            user_interactions = user_interactions[user_interactions["timestamp"] <= self.as_of_timestamp]

        hist_idx = [] if uidx is None else user_interactions.loc[user_interactions["user_idx"] == uidx, "item_idx"].tolist()
        if not hist_idx:
            return {"user_id": user_id, "known": False, "n_interactions": 0, "top_categories": [], "price_range": None, "recent_items": []}

        # Get recent items: sort by timestamp descending if available, otherwise original order
        user_hist = user_interactions[user_interactions["user_idx"] == uidx]
        if "timestamp" in user_hist.columns:
            user_hist = user_hist.sort_values("timestamp", ascending=False)
        recent_hist_idx = user_hist["item_idx"].head(MEMORY_RECENT_ITEMS).tolist()
        recent_items = [self.id2item[i] for i in recent_hist_idx if i in self.id2item]

        item_ids = [self.id2item[i] for i in hist_idx if i in self.id2item]
        placeholders = ",".join("?" for _ in item_ids)

        # Tổng hợp bằng SQL (MIN/MAX/GROUP BY): không bị giới hạn số dòng của corpus.select cắt âm thầm
        price_rows, _ = self.corpus.select(
            f"SELECT MIN(price) AS lo, MAX(price) AS hi FROM items WHERE item_id IN ({placeholders})", tuple(item_ids)
        )
        lo, hi = price_rows[0]["lo"], price_rows[0]["hi"]
        price_range = {"min": lo, "max": hi} if lo is not None else None

        cat_rows, _ = self.corpus.select(
            f"SELECT category, COUNT(*) AS n FROM item_categories WHERE item_id IN ({placeholders}) "
            "GROUP BY category ORDER BY n DESC, category LIMIT ?",
            (*item_ids, top_n_categories),
        )
        top_categories = [r["category"] for r in cat_rows]

        return {
            "user_id": user_id,
            "known": True,
            "n_interactions": len(hist_idx),
            "top_categories": top_categories,
            "price_range": price_range,
            "recent_items": recent_items,
        }
