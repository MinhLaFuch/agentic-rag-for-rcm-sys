"""
Leakage check (mục VI — BẮT BUỘC). Module này phải có khả năng phát
hiện thật khi có leakage, không chỉ pass trên dữ liệu đã đúng — test
tương ứng (tests/test_leakage_check.py) verify cả 2 chiều: pass đúng
KHI hợp lệ, raise đúng KHI vi phạm.
"""

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
