from __future__ import annotations

import numpy as np
import pandas as pd

from ._helper import _append_popular_unseen, _user_item_matrix


class PopularityRecommender:
    """Ranks items by their interaction frequency in the fitting period."""

    def fit(self, interactions: pd.DataFrame) -> "PopularityRecommender":
        self.num_items = int(interactions["item_idx"].max()) + 1
        self.scores = np.bincount(
            interactions["item_idx"].to_numpy(dtype=np.int64), minlength=self.num_items
        ).astype(np.float64)
        self.ranked_items = np.argsort(-self.scores, kind="stable")
        self.user_items = _user_item_matrix(interactions, self.num_items)
        return self

    def recommend(self, user_idx: int, top_k: int) -> list[int]:
        seen = (
            set(self.user_items.getrow(user_idx).indices.tolist())
            if 0 <= user_idx < self.user_items.shape[0]
            else set()
        )
        return _append_popular_unseen([], self.ranked_items, seen, top_k)
