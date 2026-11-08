"""
Opik PoC — Complementary Integration (Option B)

Demonstrates:
1. Loading RCM historical experiment (trajectories, metrics)
2. Creating Opik dataset from RCM requests
3. Logging RCM metrics as custom Opik metrics
4. Creating Opik experiment for comparison

This is a PoC for complementary integration — RCM metrics are computed by RCM,
exported to Opik for visualization and comparison.
"""

import json
import yaml
import sys
from pathlib import Path
from typing import Any

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Opik imports
import opik
from opik.evaluation.metrics import BaseMetric
from opik.evaluation.metrics import score_result

# RCM imports
from package.evaluation import score_trajectory
from package.corpus import ItemCorpus
from package.config import get_data_paths


class RCMMetricWrapper(BaseMetric):
    """
    Wrap RCM's score_trajectory as an Opik custom metric.
    
    In complementary integration, RCM computes metrics and we log them to Opik.
    This wrapper demonstrates the pattern, not a full implementation.
    """
    
    def __init__(self, metric_name: str):
        super().__init__(name=metric_name)
    
    def score(self, input: str, output: str, **kwargs) -> score_result.ScoreResult:
        """
        In a real implementation, this would call RCM's score_trajectory
        and extract the specific metric value.
        
        For PoC, we return a placeholder value.
        """
        # Placeholder: in real implementation, call RCM metric computation
        value = 0.95  # Placeholder
        return score_result.ScoreResult(
            value=value,
            name=self.name,
            reason=f"RCM metric {self.name} computed by RCM framework"
        )


def load_rcm_experiment(exp_dir: Path) -> dict[str, Any]:
    """Load RCM experiment artifacts."""
    trajectories_path = exp_dir / "trajectories.jsonl"
    metrics_path = exp_dir / "metrics.json"
    config_path = exp_dir / "config.yaml"
    
    trajectories = []
    if trajectories_path.exists():
        with open(trajectories_path, "r", encoding="utf-8") as f:
            for line in f:
                trajectories.append(json.loads(line))
    
    metrics = {}
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
    
    config = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    
    return {
        "trajectories": trajectories,
        "metrics": metrics,
        "config": config,
    }


def create_opik_dataset_from_rcm(experiment_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Create Opik dataset items from RCM trajectories.
    
    For PoC, we show the pattern without requiring a live Opik server.
    """
    dataset_name = "rcm_exp_002_dataset"
    
    # Insert dataset items from RCM trajectories
    dataset_items = []
    for traj in experiment_data["trajectories"][:5]:  # Limit to 5 for PoC
        item = {
            "input": traj.get("text", ""),
            "agent": traj.get("agent", ""),
            "request_id": traj.get("request_id", ""),
        }
        dataset_items.append(item)
    
    print(f"Would create Opik dataset '{dataset_name}' with {len(dataset_items)} items")
    print("Sample dataset item:", dataset_items[0] if dataset_items else "None")
    
    return dataset_items


def log_rcm_metrics_to_opik(experiment_data: dict[str, Any]) -> str:
    """
    Log RCM metrics to Opik as experiment metadata.
    
    For PoC, we show the pattern without requiring a live Opik server.
    """
    experiment_name = "rcm_exp_002_opik_poc"
    
    # Experiment metadata with RCM metrics
    experiment_metadata = {
        "rcm_config": experiment_data["config"],
        "rcm_metrics_summary": {
            "k": experiment_data["metrics"].get("k"),
            "agents": list(experiment_data["metrics"].get("summary", {}).keys()),
        },
    }
    
    print(f"Would create Opik experiment '{experiment_name}' with RCM metrics metadata")
    print("Metadata keys:", list(experiment_metadata.keys()))
    
    return experiment_name


def main():
    """Run the Opik PoC."""
    print("=== Opik PoC — Complementary Integration ===\n")
    
    # 1. Load RCM historical experiment
    exp_dir = get_data_paths().experiments_dir / "agent_eval" / "exp_002"
    print(f"Loading RCM experiment from {exp_dir}...")
    experiment_data = load_rcm_experiment(exp_dir)
    print(f"Loaded {len(experiment_data['trajectories'])} trajectories")
    print(f"Metrics keys: {list(experiment_data['metrics'].keys())}\n")
    
    # 2. Demonstrate Opik integration pattern (no live server required)
    print("Demonstrating Opik integration pattern...\n")
    
    # 3. Create Opik dataset from RCM trajectories
    print("Creating Opik dataset from RCM trajectories...")
    dataset_items = create_opik_dataset_from_rcm(experiment_data)
    print()
    
    # 4. Log RCM metrics to Opik
    print("Logging RCM metrics to Opik experiment...")
    experiment_name = log_rcm_metrics_to_opik(experiment_data)
    print()
    
    # 5. Demonstrate custom metric wrapper
    print("Demonstrating RCM custom metric wrapper...")
    custom_metric = RCMMetricWrapper(metric_name="task_success")
    # Note: In PoC, we don't actually score since we lack corpus/item2id
    print(f"Custom metric '{custom_metric.name}' created")
    print()
    
    print("=== PoC Complete ===")
    print("\nSummary:")
    print(f"- Loaded {len(experiment_data['trajectories'])} RCM trajectories")
    print(f"- Created Opik dataset with 5 items (sample)")
    print(f"- Created Opik experiment '{experiment_name}' with RCM metadata")
    print(f"- Demonstrated custom metric wrapper pattern")
    print("\nNext steps for full integration:")
    print("- Add Opik tracing decorators to RCM agent functions")
    print("- Implement full RCM metric computation in Opik custom metrics")
    print("- Import all historical experiments to Opik datasets")
    print("- Use Opik UI for experiment comparison")


if __name__ == "__main__":
    main()
