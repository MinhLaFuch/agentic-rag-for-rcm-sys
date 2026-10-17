"""Test tích hợp cho ablation comparison tool."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from package.evaluation.ablation._compare import compare_two_groups
from package.evaluation.ablation._limits import AblationLimits


def test_end_to_end_with_synthetic_data():
    """Test end-to-end với dữ liệu tổng hợp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Tạo thư mục experiments giả
        exp_dir_a = tmpdir / "exp_001"
        exp_dir_b = tmpdir / "exp_002"
        exp_dir_a.mkdir(parents=True)
        exp_dir_b.mkdir(parents=True)
        
        # Tạo config.yaml cho exp_001
        config_a = {
            "config": {
                "seed": 42,
                "per_segment": 2,
                "language": "vi",
                "k": 10,
            },
            "dataset": {
                "eval_on": "validation",
            },
        }
        (exp_dir_a / "config.yaml").write_text(yaml.dump(config_a), encoding="utf-8")
        
        # Tạo config.yaml cho exp_002 (cấu hình giống nhau)
        config_b = config_a.copy()
        (exp_dir_b / "config.yaml").write_text(yaml.dump(config_b), encoding="utf-8")
        
        # Tạo scored.jsonl cho exp_001
        scored_a = [
            {"request_id": "req1", "agent": "planner", "kind": "similar", "segment": "sparse", "task_success": True, "recall@10": 0.5, "ndcg@10": 0.3, "text": "test1"},
            {"request_id": "req2", "agent": "planner", "kind": "similar", "segment": "sparse", "task_success": False, "recall@10": 0.0, "ndcg@10": 0.0, "text": "test2"},
        ]
        (exp_dir_a / "scored.jsonl").write_text("\n".join(json.dumps(d) for d in scored_a), encoding="utf-8")
        
        # Tạo scored.jsonl cho exp_002
        scored_b = [
            {"request_id": "req1", "agent": "planner_memory", "kind": "similar", "segment": "sparse", "task_success": True, "recall@10": 0.6, "ndcg@10": 0.4, "text": "test1"},
            {"request_id": "req2", "agent": "planner_memory", "kind": "similar", "segment": "sparse", "task_success": True, "recall@10": 0.1, "ndcg@10": 0.05, "text": "test2"},
        ]
        (exp_dir_b / "scored.jsonl").write_text("\n".join(json.dumps(d) for d in scored_b), encoding="utf-8")
        
        # Chuẩn bị group data
        group_a = {
            "group_name": "config_a",
            "configs": [config_a],
            "scored": [scored_a],
            "exp_dirs": [exp_dir_a],
        }
        group_b = {
            "group_name": "config_b",
            "configs": [config_b],
            "scored": [scored_b],
            "exp_dirs": [exp_dir_b],
        }
        
        # Tạo limits giả
        limits = AblationLimits(
            bootstrap_resamples=100,
            confidence=0.95,
            min_n_warn=20,
            seed=42,
            metrics=["task_success", "recall@10", "ndcg@10"],
            groups={},
            contrasts=[],
            output_subdir="test",
        )
        
        # So sánh
        results = compare_two_groups(
            group_a,
            group_b,
            "planner",
            "planner_memory",
            kinds=None,
            k=10,
            limits=limits,
        )
        
        # Kiểm tra kết quả
        assert "error" not in results
        assert results["n_pairs"] == 2
        assert "all_kinds" in results
        assert "similar" in results["all_kinds"]
        
        # Kiểm tra metric task_success
        task_success_data = results["all_kinds"]["similar"]["task_success"]
        assert task_success_data["n"] == 2
        assert task_success_data["mean_a"] == 0.5  # (True + False) / 2
        assert task_success_data["mean_b"] == 1.0  # (True + True) / 2
        assert task_success_data["diff"] == 0.5  # 1.0 - 0.5
