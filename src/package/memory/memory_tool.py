"""
MemoryTool (bản "nhẹ" — phương án A).

Amazon Reviews 2023 không có hội thoại multi-turn, nên không có gì để LLM
trích preference ra (kiểu InteRecAgent's UserProfileMemory). Bản này chỉ
retrieve: tổng hợp thống kê từ chính interaction history + ItemCorpus đã có
sẵn (category hay mua, khoảng giá) — không write/update/forget, vì không có
nguồn hội thoại nào để ghi vào.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from ..tools.base import Tool, ToolInputError
from ..tools.corpus import ItemCorpus


class MemoryTool(Tool):
    name = "MemoryTool"
    description = (
        "Retrieve a lightweight summary of a user's past purchase pattern "
        "(top categories, price range) derived from their interaction history. "
        "Read-only — no write/update, since there is no dialogue to extract "
        "preferences from in this dataset."
    )
    input_schema = {
        "user_id": "str",
        "top_n_categories": "int (default 3)",
    }

    def __init__(
        self,
        interactions: pd.DataFrame,
        user2id: dict[str, int],
        item2id: dict[str, int],
        corpus: ItemCorpus,
        logger=None,
    ) -> None:
        super().__init__(logger)
        self.interactions = interactions
        self.user2id = user2id
        self.id2item = {v: k for k, v in item2id.items()}
        self.corpus = corpus

    def execute(self, user_id: str, top_n_categories: int = 3) -> dict[str, Any]:
        if user_id not in self.user2id:
            raise ToolInputError(f"unknown user_id: {user_id!r}")
        uidx = self.user2id[user_id]
        hist_idx = self.interactions.loc[self.interactions["user_idx"] == uidx, "item_idx"].tolist()
        if not hist_idx:
            return {"user_id": user_id, "known": True, "n_interactions": 0, "top_categories": [], "price_range": None}

        item_ids = [self.id2item[i] for i in hist_idx if i in self.id2item]
        placeholders = ",".join("?" for _ in item_ids)

        price_rows, _ = self.corpus.select(
            f"SELECT price FROM items WHERE item_id IN ({placeholders}) AND price IS NOT NULL", tuple(item_ids)
        )
        prices = [r["price"] for r in price_rows]
        price_range = {"min": min(prices), "max": max(prices)} if prices else None

        cat_rows, _ = self.corpus.select(
            f"SELECT category FROM item_categories WHERE item_id IN ({placeholders})", tuple(item_ids)
        )
        top_categories = [c for c, _ in Counter(r["category"] for r in cat_rows).most_common(top_n_categories)]

        return {
            "user_id": user_id,
            "known": True,
            "n_interactions": len(hist_idx),
            "top_categories": top_categories,
            "price_range": price_range,
        }
