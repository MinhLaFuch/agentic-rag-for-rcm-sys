"""Hàm lấy sample requests và sample users cho demo."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from package.agents.evaluation._schema import TEMPLATES
from package.config import load_config


def sample_requests(language: str = "vi") -> dict[str, str]:
    """Trả về các request mẫu cho từng kind."""
    templates = TEMPLATES.get(language, TEMPLATES["vi"])
    return {
        "similar": templates["similar"].format(user_id="user123", item_id="Video_Games::B00EXAMPLE", k=5),
        "personalized": templates["personalized"].format(user_id="user123", k=5),
        "constrained": templates["constrained"].format(user_id="user123", category="Video Games", price_max=50, k=5),
        "cold_text": templates["cold_text"].format(user_id="user456", category="Toys", k=5),
        "ambiguous": templates["ambiguous"][0],  # "Gợi ý cho tôi sản phẩm hay."
    }


def sample_users(
    fit_df: pd.DataFrame,
    user2id: dict[str, int],
    n_per_segment: int = 3,
    sparse_max: int = 5,
) -> dict[str, list[str]]:
    """Chọn vài user_id thật theo segment (cold/sparse/warm)."""
    id2user = {v: k for k, v in user2id.items()}
    num_users = len(user2id)
    hist_size = np.bincount(fit_df["user_idx"].to_numpy(), minlength=num_users)

    cold_users = [id2user[i] for i, h in enumerate(hist_size) if h == 0][:n_per_segment]
    sparse_users = [id2user[i] for i, h in enumerate(hist_size) if 0 < h <= sparse_max][:n_per_segment]
    warm_users = [id2user[i] for i, h in enumerate(hist_size) if h > sparse_max][:n_per_segment]

    return {
        "cold": cold_users,
        "sparse": sparse_users,
        "warm": warm_users,
    }
