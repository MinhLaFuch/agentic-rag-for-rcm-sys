"""
Leakage check (mục VI — BẮT BUỘC). Module này phải có khả năng phát
hiện thật khi có leakage, không chỉ pass trên dữ liệu đã đúng — test
tương ứng (tests/test_leakage_check.py) verify cả 2 chiều: pass đúng
KHI hợp lệ, raise đúng KHI vi phạm.
"""

from __future__ import annotations


class LeakageError(RuntimeError):
    """Raised khi phát hiện data leakage theo thời gian."""
