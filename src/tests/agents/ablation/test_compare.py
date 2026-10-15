"""Test cho module compare ablation."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from package.agents.ablation._compare import (
    average_across_runs,
    compute_binary_disagreement,
    compute_metric_diff,
    find_disagreements,
    pair_by_request_id,
)
from package.agents.ablation._limits import AblationLimits


def test_pair_by_request_id():
    """Ghép cặp theo request_id phải trả list tuple."""
    scored_a = [
        {"request_id": "req1", "agent": "planner", "task_success": True},
        {"request_id": "req2", "agent": "planner", "task_success": False},
    ]
    scored_b = [
        {"request_id": "req1", "agent": "planner_memory", "task_success": True},
        {"request_id": "req2", "agent": "planner_memory", "task_success": True},
    ]
    
    pairs = pair_by_request_id(scored_a, scored_b, "planner", "planner_memory")
    
    assert len(pairs) == 2
    assert pairs[0][0]["request_id"] == "req1"
    assert pairs[0][1]["request_id"] == "req1"
    assert pairs[1][0]["request_id"] == "req2"
    assert pairs[1][1]["request_id"] == "req2"


def test_pair_by_request_id_different_agents():
    """Ghép cặp phải chỉ lấy đúng agent."""
    scored_a = [
        {"request_id": "req1", "agent": "planner", "task_success": True},
        {"request_id": "req2", "agent": "baseline", "task_success": False},
    ]
    scored_b = [
        {"request_id": "req1", "agent": "planner_memory", "task_success": True},
        {"request_id": "req2", "agent": "planner_memory", "task_success": True},
    ]
    
    pairs = pair_by_request_id(scored_a, scored_b, "planner", "planner_memory")
    
    assert len(pairs) == 1  # chỉ req1


def test_average_across_runs():
    """Trung bình qua nhiều lần chạy phải tính đúng."""
    scored_list = [
        [
            {"request_id": "req1", "agent": "planner", "recall@10": 0.5, "task_success": True},
            {"request_id": "req2", "agent": "planner", "recall@10": 0.6, "task_success": False},
        ],
        [
            {"request_id": "req1", "agent": "planner", "recall@10": 0.7, "task_success": True},
            {"request_id": "req2", "agent": "planner", "recall@10": 0.8, "task_success": True},
        ],
    ]
    
    averaged = average_across_runs(scored_list, "planner")
    
    assert len(averaged) == 2
    assert averaged["req1"]["recall@10"] == 0.6  # (0.5 + 0.7) / 2
    assert averaged["req2"]["recall@10"] == 0.7  # (0.6 + 0.8) / 2
    # task_success không trung bình, giữ nguyên từ lần chạy đầu tiên
    assert averaged["req1"]["task_success"] is True


def test_compute_metric_diff():
    """Tính hiệu metric phải trả đúng kết quả."""
    pairs = [
        ({"recall@10": 0.5}, {"recall@10": 0.7}),
        ({"recall@10": 0.6}, {"recall@10": 0.8}),
    ]
    
    limits = AblationLimits(
        bootstrap_resamples=100,
        confidence=0.95,
        min_n_warn=20,
        seed=42,
        metrics=["recall@10"],
        groups={},
        contrasts=[],
        output_subdir="test",
    )
    
    result = compute_metric_diff(pairs, "recall@10", k=10, limits=limits)
    
    assert result["n"] == 2
    assert result["mean_a"] == 0.55  # (0.5 + 0.6) / 2
    assert result["mean_b"] == 0.75  # (0.7 + 0.8) / 2
    assert abs(result["diff"] - 0.2) < 1e-6  # 0.75 - 0.55 (floating point)


def test_compute_metric_diff_empty():
    """Tính hiệu với list rỗng phải trả n=0."""
    pairs = []
    
    limits = AblationLimits(
        bootstrap_resamples=100,
        confidence=0.95,
        min_n_warn=20,
        seed=42,
        metrics=["recall@10"],
        groups={},
        contrasts=[],
        output_subdir="test",
    )
    
    result = compute_metric_diff(pairs, "recall@10", k=10, limits=limits)
    
    assert result["n"] == 0


def test_compute_binary_disagreement():
    """Đếm không nhất quán cho metric nhị phân phải đúng."""
    pairs = [
        ({"task_success": True}, {"task_success": True}),  # both correct
        ({"task_success": True}, {"task_success": False}),  # A correct, B wrong
        ({"task_success": False}, {"task_success": True}),  # A wrong, B correct
        ({"task_success": False}, {"task_success": False}),  # both wrong
    ]
    
    counts = compute_binary_disagreement(pairs, "task_success")
    
    assert counts["n_correct_both"] == 1
    assert counts["n_a_correct_b_wrong"] == 1
    assert counts["n_a_wrong_b_correct"] == 1
    assert counts["n_both_wrong"] == 1


def test_find_disagreements():
    """Tìm các request khác nhau phải trả list đúng."""
    pairs = [
        (
            {"request_id": "req1", "text": "test1", "kind": "similar", "segment": "sparse", "task_success": True, "plan": [], "steps": [], "reflections": 0},
            {"request_id": "req1", "text": "test1", "kind": "similar", "segment": "sparse", "task_success": False, "plan": [], "steps": [], "reflections": 0},
        ),
        (
            {"request_id": "req2", "text": "test2", "kind": "similar", "segment": "sparse", "task_success": True, "plan": [], "steps": [], "reflections": 0},
            {"request_id": "req2", "text": "test2", "kind": "similar", "segment": "sparse", "task_success": True, "plan": [], "steps": [], "reflections": 0},
        ),
    ]
    
    disagreements = find_disagreements(pairs, "task_success")
    
    assert len(disagreements) == 1
    assert disagreements[0]["request_id"] == "req1"
    assert disagreements[0]["text"] == "test1"
