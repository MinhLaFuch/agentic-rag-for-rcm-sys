"""Test cho config demo.yaml."""

import pytest

from package.demo._limits import get_demo_limits


def test_get_demo_limits_loads_correct_values():
    """get_demo_limits phải load đúng giá trị từ configs/agent/demo.yaml."""
    limits = get_demo_limits()
    assert limits.max_error_length == 300
    assert limits.max_items_display == 10
    assert limits.sample_users_per_segment == 3
    assert limits.default_language == "vi"


def test_get_demo_limits_is_cached():
    """get_demo_limits phải dùng lru_cache (gọi nhiều lần trả cùng object)."""
    limits1 = get_demo_limits()
    limits2 = get_demo_limits()
    assert limits1 is limits2
