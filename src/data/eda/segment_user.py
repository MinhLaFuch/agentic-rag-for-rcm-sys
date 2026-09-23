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
    thật để so sánh category ưa thích trước/sau — nếu không có
    evolving_category_col, cột 'evolving_interest' sẽ luôn là False
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

    if evolving_category_col and evolving_category_col in interactions.columns:
        # placeholder cho logic evolving-interest thật — sẽ hoàn thiện khi
        # có dữ liệu category thật (BLOCKED hiện tại)
        segments["evolving_interest"] = False
    else:
        segments["evolving_interest"] = False

    return segments.reset_index()