"""Lấy lịch sử item của 1 user từ bảng interactions đã xử lý."""
import pandas as pd


def get_user_history(interactions: pd.DataFrame, user_idx: int, split: str | None = "train") -> list[int]:
    # split="train": lịch sử "user đã biết" (agent, backend train)
    # split=None: lấy toàn bộ, kể cả val/test — chỉ dùng khi debug/kiểm tra, không dùng lúc train/eval
    df = interactions[interactions.user_idx == user_idx]
    if split is not None:
        df = df[df.split == split]
    return df.sort_values("timestamp")["item_idx"].tolist()
