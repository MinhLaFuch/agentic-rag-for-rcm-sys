"""Test cho module thống kê ablation."""

import pytest

from package.evaluation.ablation._statistics import bootstrap_ci, mcnemar_test


def test_bootstrap_ci_with_known_values():
    """Bootstrap CI phải trả khoảng tin cậy đúng với seed cố định."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    ci_lower, ci_upper = bootstrap_ci(values, n_resamples=1000, confidence=0.95, seed=42)
    
    # Khoảng tin cậy phải hợp lý (không phải 0,0)
    assert ci_lower < ci_upper
    assert 0 < ci_lower < 5
    assert 0 < ci_upper < 5


def test_bootstrap_ci_reproducible():
    """Bootstrap CI phải tái lập với cùng seed."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    
    ci1 = bootstrap_ci(values, n_resamples=1000, confidence=0.95, seed=42)
    ci2 = bootstrap_ci(values, n_resamples=1000, confidence=0.95, seed=42)
    
    assert ci1 == ci2


def test_bootstrap_ci_empty():
    """Bootstrap CI với list rỗng phải trả (0, 0)."""
    ci_lower, ci_upper = bootstrap_ci([], n_resamples=1000, confidence=0.95, seed=42)
    assert ci_lower == 0.0
    assert ci_upper == 0.0


def test_mcnemar_test_sufficient_data():
    """McNemar test phải trả b, c, p khi đủ dữ liệu."""
    # b=10, c=5 (cặp không nhất quán đủ)
    result = mcnemar_test(
        n_correct_both=80,
        n_a_correct_b_wrong=10,
        n_a_wrong_b_correct=5,
        n_both_wrong=5,
    )
    
    assert result is not None
    b, c, p = result
    assert b == 10.0
    assert c == 5.0
    assert 0 < p <= 1


def test_mcnemar_test_insufficient_data():
    """McNemar test phải trả None khi không đủ cặp không nhất quán."""
    result = mcnemar_test(
        n_correct_both=95,
        n_a_correct_b_wrong=3,
        n_a_wrong_b_correct=2,
        n_both_wrong=0,
    )
    
    assert result is None  # b + c = 5 < 10


def test_mcnemar_test_perfect_agreement():
    """McNemar test với hoàn toàn đồng thuận phải trả None."""
    result = mcnemar_test(
        n_correct_both=100,
        n_a_correct_b_wrong=0,
        n_a_wrong_b_correct=0,
        n_both_wrong=0,
    )
    
    assert result is None  # b + c = 0 < 10
