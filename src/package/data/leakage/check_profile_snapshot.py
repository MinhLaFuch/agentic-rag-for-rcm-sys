"""Leakage check: dữ liệu dùng làm profile/history không được có timestamp sau mốc as_of."""

from __future__ import annotations

import pandas as pd

from ._error import LeakageError


def check_profile_snapshot(
    as_of_timestamp: int, source_interactions: pd.DataFrame
) -> None:
    """
    Verify rằng mọi interaction dùng để build profile tại thời điểm
    `as_of_timestamp` có timestamp <= as_of_timestamp (mục VI: "profile
    tại thời điểm t chỉ được phép dùng information <= t").

    Raise LeakageError nếu có bất kỳ dòng nào timestamp > as_of_timestamp.
    """
    future_rows = source_interactions[
        source_interactions["timestamp"] > as_of_timestamp
    ]
    if len(future_rows) > 0:
        raise LeakageError(
            f"Profile snapshot leakage at t={as_of_timestamp}: "
            f"{len(future_rows)} interaction(s) with timestamp in the future "
            f"(max found: {future_rows['timestamp'].max()})"
        )
