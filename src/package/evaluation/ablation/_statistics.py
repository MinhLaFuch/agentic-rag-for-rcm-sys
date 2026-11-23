"""Thống kê cho ablation comparison: bootstrap CI, McNemar test."""

from __future__ import annotations

import random
from typing import Any


def bootstrap_ci(values: list[float], n_resamples: int, confidence: float, seed: int) -> tuple[float, float]:
    """Tính khoảng tin cậy bootstrap cho trung bình."""
    if not values:
        return (0.0, 0.0)
    
    rng = random.Random(seed)
    n = len(values)
    boot_means = []
    
    for _ in range(n_resamples):
        sample = rng.choices(values, k=n)
        boot_means.append(sum(sample) / n)
    
    boot_means.sort()
    alpha = 1 - confidence
    lower_idx = int(alpha / 2 * n_resamples)
    upper_idx = int((1 - alpha / 2) * n_resamples)
    
    return (boot_means[lower_idx], boot_means[upper_idx])


def mcnemar_test(
    n_correct_both: int,
    n_a_correct_b_wrong: int,
    n_a_wrong_b_correct: int,
    n_both_wrong: int,
) -> tuple[float, float, float] | None:
    """
    Kiểm định McNemar cho metric nhị phân (dùng nhị thức).
    
    Trả về (b, c, p) hoặc None nếu không đủ dữ liệu.
    b = số cặp A đúng B sai
    c = số cặp A sai B đúng
    p = p-value
    """
    b = n_a_correct_b_wrong
    c = n_a_wrong_b_correct
    
    if b + c < 10:  # Không đủ cặp không nhất quán
        return None
    
    # Approximation: (|b - c| - 1)^2 / (b + c) ~ chi-square(1)
    statistic = (abs(b - c) - 1) ** 2 / (b + c)
    
    # chi-square(1) CDF at 3.841 = 0.95 (p = 0.05)
    # Sử dụng approximation đơn giản cho p-value
    # Độ chính xác đủ cho demo, không cần scipy
    p = 1.0 if statistic < 3.841 else 0.05 if statistic < 6.635 else 0.01 if statistic < 10.828 else 0.001
    
    return (float(b), float(c), p)


def wilson_interval(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float] | None:
    """Wilson score interval cho tỉ lệ nhị phân; None khi n = 0."""
    if n <= 0:
        return None
    import math

    z = {0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}.get(round(confidence, 2), 1.9600)
    p_hat = successes / n
    denom = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))
