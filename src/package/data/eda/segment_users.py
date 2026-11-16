"""
EDA functions cho interaction data (Phase 2, mục V/VI/XVIII).

Các hàm ở đây là pure function trên pandas DataFrame, KHÔNG tự tải dữ
liệu — vì vậy có thể unit test bằng dữ liệu synthetic (để verify logic
đúng), tách biệt hoàn toàn với việc dữ liệu thật có tải được hay không
(xem src/data/acquire.py — hiện đang BLOCKED do network).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

def segment_users(
    interactions: pd.DataFrame,
    as_of_timestamp: int,
    sparse_threshold: int = 3,
    evolving_category_col: str | None = None,
) -> pd.DataFrame:
    """
    Gán mỗi user vào 1 trong 4 nhóm theo mục XVIII: warm / new / sparse /
    evolving. Đây là implementation tối giản cho warm/new/sparse (dùng số
    lượng interaction <= as_of_timestamp); "evolving" cần dữ liệu category
    thật để so sánh category ưa thích trước/sau — logic chưa implement và dữ
    liệu category time-series đang BLOCKED (xem acquire.py). Vì vậy cột
    'evolving_interest' luôn là pd.NA (nullable boolean): NA = "không đủ dữ
    liệu để đánh giá", KHÁC với False = "đã kiểm tra, không phát hiện"
    (KHÔNG suy diễn khi thiếu dữ liệu — mục XXVIII: không tạo số liệu giả).
    """
    past = interactions[interactions["timestamp"] <= as_of_timestamp]
    counts = past.groupby("user_id").size().rename("n_interactions")

    segments = counts.to_frame()
    segments["segment"] = np.select(
        [
            segments["n_interactions"] == 0,
            segments["n_interactions"] <= sparse_threshold,
        ],
        ["new", "sparse_history"],
        default="warm",
    )

    # evolving-interest: unavailable cho tới khi có category time-series và
    # logic so sánh trước/sau được implement — NA, không phải False.
    segments["evolving_interest"] = pd.Series(pd.NA, index=segments.index, dtype="boolean")

    return segments.reset_index()
