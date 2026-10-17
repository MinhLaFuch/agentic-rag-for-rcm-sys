"""Test cho module limits ablation."""

import pytest

from package.agents.ablation._limits import AblationLimits
from package.config.load_config import ConfigError


def test_ablation_limits_creation():
    """AblationLimits phải tạo được dataclass hợp lệ."""
    limits = AblationLimits(
        bootstrap_resamples=10000,
        confidence=0.95,
        min_n_warn=20,
        seed=42,
        metrics=["task_success"],
        groups={},
        contrasts=[],
        output_subdir="test",
    )
    assert limits.bootstrap_resamples == 10000
    assert limits.confidence == 0.95
    assert limits.min_n_warn == 20
    assert limits.seed == 42
    assert limits.metrics == ["task_success"]
    assert limits.groups == {}
    assert limits.contrasts == []
    assert limits.output_subdir == "test"

