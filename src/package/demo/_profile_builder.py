"""Build DemoProfile list từ nhiều nguồn (blank, pinned, auto)."""

from __future__ import annotations

import warnings
from typing import Any

import pandas as pd

from ..config.load_config import load_config
from ._limits import get_demo_limits
from .samples import sample_users
from .view import DemoProfile


def build_profiles(
    fit_df: pd.DataFrame,
    user2id: dict[str, int],
    config_name: str = "agent/demo_profiles",
) -> list[DemoProfile]:
    """Xây danh sách profile từ blank, pinned, và auto profiles."""
    profiles: list[DemoProfile] = []

    # 1. Blank profile (luôn có, mặc định)
    profiles.append(
        DemoProfile(
            profile_id="blank",
            label="New user (no history)",
            description="Blank profile for testing cold-start behavior",
            user_id=None,
            segment="blank",
        )
    )

    # 2. Pinned profiles từ config (nếu có)
    try:
        cfg = load_config(config_name)
        pinned_list = cfg.get("demo_profiles", {}).get("pinned", [])
        for pinned in pinned_list:
            user_id = pinned.get("user_id")
            if user_id is None:
                warnings.warn(f"Pinned profile missing user_id: {pinned}")
                continue
            if user_id not in user2id:
                warnings.warn(f"Pinned profile user_id not in mapping: {user_id}")
                continue
            profiles.append(
                DemoProfile(
                    profile_id=pinned.get("id", f"pinned_{user_id}"),
                    label=pinned.get("label", f"Pinned: {user_id}"),
                    description=pinned.get("description", ""),
                    user_id=user_id,
                    segment="pinned",
                )
            )
    except Exception as exc:
        # Config không tồn tại hoặc lỗi: chỉ cảnh báo, không crash
        warnings.warn(f"Failed to load pinned profiles: {exc}")

    # 3. Auto profiles từ data (cold/sparse/warm)
    n_per_segment = get_demo_limits().sample_users_per_segment
    sparse_max = 5
    sample_dict = sample_users(fit_df, user2id, n_per_segment=n_per_segment, sparse_max=sparse_max)

    for segment, user_ids in sample_dict.items():
        for user_id in user_ids:
            # Lấy số interactions để nhãn ngắn gọn
            user_internal_id = user2id.get(user_id)
            n_interactions = 0
            if user_internal_id is not None:
                n_interactions = (fit_df["user_idx"] == user_internal_id).sum()

            # Xác định domain từ lịch sử (nếu có)
            domain = "Unknown"
            if user_internal_id is not None and not fit_df.empty:
                user_hist = fit_df[fit_df["user_idx"] == user_internal_id]
                if not user_hist.empty:
                    # Lấy item đầu tiên và trích domain từ item_id (format: Domain::asin)
                    first_item_internal_id = user_hist.iloc[0]["item_idx"]
                    # Không có id2item ở đây, nên tạm bỏ qua domain
                    pass

            label = f"{segment} · {n_interactions} interactions"
            description = f"Auto-generated {segment} profile with {n_interactions} interactions"

            profiles.append(
                DemoProfile(
                    profile_id=f"auto_{segment}_{user_id}",
                    label=label,
                    description=description,
                    user_id=user_id,
                    segment=segment,
                )
            )

    return profiles
