"""
MemoryTool (bản "nhẹ" — phương án A).

Amazon Reviews 2023 không có hội thoại multi-turn, nên không có gì để LLM
trích preference ra (kiểu InteRecAgent's UserProfileMemory). Bản này chỉ
retrieve: tổng hợp thống kê từ chính interaction history + ItemCorpus đã có
sẵn (category hay mua, khoảng giá, love/hate preferences) — không write/update/forget, vì không có
nguồn hội thoại nào để ghi vào.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..agents._limits import get_memory_limits
from ..data.leakage import check_profile_snapshot
from ..tools.base import Tool, validate_int
from ..tools.corpus import ItemCorpus


class MemoryTool(Tool):
    name = "MemoryTool"
    description = (
        "Retrieve a lightweight summary of a user's past purchase pattern "
        "(top categories, price range, recent items, love/hate preferences) derived from their interaction history. "
        "Read-only — no write/update, since there is no dialogue to extract "
        "preferences from in this dataset."
    )
    input_schema = {
        "user_id": "str",
    }
    output_schema = {
        "user_id": "str", "known": "bool  -- False = no history (unknown user or 0 interactions: cold start)", "n_interactions": "int",
        "top_categories": "list[str]  -- e.g. use as filters.categories_any via \"$1.top_categories\"",
        "price_range": "{min, max} | None  -- e.g. \"$1.price_range.max\" for filters.price_max",
        "recent_items": "list[str]  -- namespaced item ids, most recent first; use as ItemCFTool.items via \"$1.recent_items\"",
        "love_categories": "list[str]  -- categories the user likes (rating >= love_min_rating)",
        "hate_categories": "list[str]  -- categories the user dislikes (rating <= hate_max_rating)",
        "loved_items": "list[str]  -- item ids the user loves most (highest-rated items)",
        "hated_items": "list[str]  -- item ids the user hates most (lowest-rated items)",
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
        self.item2id = item2id
        self.id2item = {v: k for k, v in item2id.items()}
        self.corpus = corpus
        self.as_of_timestamp = as_of_timestamp
        self.limits = get_memory_limits()

    def execute(self, user_id: str, top_n_categories: int | None = None) -> dict[str, Any]:
        uidx = self.user2id.get(user_id)  # user lạ hoặc 0 tương tác: known=False (cold-start, như RecoModelTool), không ném lỗi
        if top_n_categories is None:
            top_n_categories = self.limits.top_n_categories

        # Apply as_of_timestamp filter if set (leakage prevention)
        user_interactions = self.interactions
        if self.as_of_timestamp is not None and "timestamp" in user_interactions.columns:
            user_interactions = user_interactions[user_interactions["timestamp"] <= self.as_of_timestamp]

        hist = user_interactions.loc[user_interactions["user_idx"] == uidx] if uidx is not None else pd.DataFrame()
        if hist.empty:
            return {
                "user_id": user_id, "known": False, "n_interactions": 0,
                "top_categories": [], "price_range": None, "recent_items": [],
                "love_categories": [], "hate_categories": [], "loved_items": [], "hated_items": [],
            }

        # Get recent items: sort by timestamp descending if available, otherwise original order
        if "timestamp" in hist.columns:
            hist_sorted = hist.sort_values("timestamp", ascending=False)
        else:
            hist_sorted = hist
        recent_hist_idx = hist_sorted["item_idx"].head(self.limits.recent_items).tolist()
        recent_items = [self.id2item[i] for i in recent_hist_idx if i in self.id2item]

        hist_idx = hist["item_idx"].tolist()
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

        # Love/hate categories and items (requires rating column)
        love_categories = []
        hate_categories = []
        loved_items = []
        hated_items = []
        loved_items_sorted = []
        hated_items_sorted = []

        if "rating" in hist.columns:
            # Compute category-level love/hate based on ratings
            hist_with_rating = hist.merge(
                hist.groupby("item_idx")["rating"].mean().reset_index(),
                on="item_idx",
                suffixes=("", "_avg")
            )
            
            # Get categories for each item
            cat_rows_all, _ = self.corpus.select(
                f"SELECT item_id, category FROM item_categories WHERE item_id IN ({placeholders})", tuple(item_ids)
            )
            item_to_cats = {}
            for row in cat_rows_all:
                item_to_cats.setdefault(row["item_id"], []).append(row["category"])

            # Build love/hate lists
            for _, row in hist.iterrows():
                item_id = self.id2item.get(row["item_idx"])
                if item_id is None:
                    continue
                rating = row["rating"]
                cats = item_to_cats.get(item_id, [])
                
                if rating >= self.limits.love_min_rating:
                    love_categories.extend(cats)
                    loved_items.append(item_id)
                elif rating <= self.limits.hate_max_rating:
                    hate_categories.extend(cats)
                    hated_items.append(item_id)

            # Deduplicate and limit
            love_categories = list(dict.fromkeys(love_categories))[:top_n_categories]
            hate_categories = list(dict.fromkeys(hate_categories))[:top_n_categories]
            
            # Sort loved/hated items by rating and limit
            item_ratings = hist.groupby("item_idx")["rating"].mean().to_dict()
            loved_items_sorted = sorted(
                set(loved_items), 
                key=lambda x: item_ratings.get(self.item2id.get(x, -1), 0), 
                reverse=True
            )[:self.limits.top_n_loved_items]
            hated_items_sorted = sorted(
                set(hated_items),
                key=lambda x: item_ratings.get(self.item2id.get(x, -1), 5)
            )[:self.limits.top_n_hated_items]

        return {
            "user_id": user_id,
            "known": True,
            "n_interactions": len(hist_idx),
            "top_categories": top_categories,
            "price_range": price_range,
            "recent_items": recent_items,
            "love_categories": love_categories,
            "hate_categories": hate_categories,
            "loved_items": loved_items_sorted,
            "hated_items": hated_items_sorted,
        }
