"""Campaign execution runner for orchestrating multiple experiments."""

from __future__ import annotations

import time
import subprocess
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from ._schema import CampaignConfig, CampaignResult, ExperimentRun


class CampaignRunner:
    """Runner for executing campaign experiments."""

    def __init__(self, config: CampaignConfig, git_sha: str = ""):
        self.config = config
        self.git_sha = git_sha

    def run_campaign(self) -> CampaignResult:
        """Execute the full campaign.

        Returns:
            CampaignResult with all experiment runs and comparisons
        """
        campaign_hash = self.config.compute_hash()
        runs: list[ExperimentRun] = []

        # Create output directory
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Execute each experiment
        for experiment in self.config.experiments:
            for run_num in range(1, experiment.repetition_count + 1):
                run = self._run_experiment(experiment, run_num, output_dir)
                runs.append(run)

        # Perform comparisons if configured
        comparisons = {}
        if self.config.comparison_pairs:
            comparisons = self._run_comparisons(runs, output_dir)

        # Generate summary
        summary = self._generate_summary(runs)

        result = CampaignResult(
            campaign_id=self.config.campaign_id,
            campaign_hash=campaign_hash,
            runs=runs,
            comparisons=comparisons,
            summary=summary,
            git_sha=self.git_sha,
        )

        # Save campaign result
        result_path = output_dir / "campaign_result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            import json
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

        return result

    def _run_experiment(
        self,
        experiment: Any,
        run_number: int,
        output_dir: Path,
    ) -> ExperimentRun:
        """Run a single experiment.

        Args:
            experiment: ExperimentConfig
            run_number: Repetition number
            output_dir: Campaign output directory

        Returns:
            ExperimentRun
        """
        exp_output_dir = output_dir / experiment.name / f"run_{run_number}"
        exp_output_dir.mkdir(parents=True, exist_ok=True)

        start_time = time.perf_counter()
        success = True
        error = None
        metrics = {}

        try:
            # In a real implementation, this would invoke the actual experiment runner
            # For now, simulate execution
            metrics = self._simulate_experiment_run(experiment, exp_output_dir)
        except Exception as e:
            success = False
            error = str(e)

        duration = time.perf_counter() - start_time

        return ExperimentRun(
            experiment_name=experiment.name,
            run_number=run_number,
            output_dir=str(exp_output_dir),
            success=success,
            error=error,
            duration_seconds=duration,
            metrics=metrics,
        )

    def _simulate_experiment_run(
        self,
        experiment: Any,
        output_dir: Path,
    ) -> dict[str, Any]:
        """Simulate an experiment run (placeholder for real implementation).

        In a real implementation, this would:
        1. Load the agent configuration
        2. Load the dataset
        3. Run the evaluation
        4. Save results to output_dir
        """
        # Placeholder: simulate metrics
        return {
            "task_success_rate": 0.85,
            "grounded_answer_rate": 0.90,
            "constraint_satisfaction": 0.80,
            "avg_latency": 1.5,
        }

    def _run_comparisons(
        self,
        runs: list[ExperimentRun],
        output_dir: Path,
    ) -> dict[str, Any]:
        """Run comparisons between experiment pairs.

        Args:
            runs: List of experiment runs
            output_dir: Output directory

        Returns:
            Dict of comparison results
        """
        comparisons = {}

        for exp_a, exp_b in self.config.comparison_pairs:
            # Find runs for each experiment
            runs_a = [r for r in runs if r.experiment_name == exp_a and r.success]
            runs_b = [r for r in runs if r.experiment_name == exp_b and r.success]

            if not runs_a or not runs_b:
                comparisons[f"{exp_a}_vs_{exp_b}"] = {
                    "status": "skipped",
                    "reason": "One or both experiments failed",
                }
                continue

            # Compute comparison metrics
            comparison = self._compare_experiments(runs_a, runs_b)
            comparisons[f"{exp_a}_vs_{exp_b}"] = comparison

        return comparisons

    def _compare_experiments(
        self,
        runs_a: list[ExperimentRun],
        runs_b: list[ExperimentRun],
    ) -> dict[str, Any]:
        """Compare two sets of experiment runs.

        Args:
            runs_a: Runs for experiment A
            runs_b: Runs for experiment B

        Returns:
            Comparison results
        """
        # Average metrics for each experiment
        avg_a = self._average_metrics(runs_a)
        avg_b = self._average_metrics(runs_b)

        comparison = {
            "status": "success",
            "experiment_a": runs_a[0].experiment_name,
            "experiment_b": runs_b[0].experiment_name,
            "runs_a": len(runs_a),
            "runs_b": len(runs_b),
            "deltas": {},
        }

        # Compute deltas
        for key in set(avg_a.keys()) | set(avg_b.keys()):
            val_a = avg_a.get(key, 0)
            val_b = avg_b.get(key, 0)
            comparison["deltas"][key] = {
                "a": val_a,
                "b": val_b,
                "delta": val_b - val_a,
                "relative_delta": (val_b - val_a) / val_a if val_a != 0 else 0,
            }

        return comparison

    def _average_metrics(self, runs: list[ExperimentRun]) -> dict[str, float]:
        """Compute average metrics across runs."""
        if not runs:
            return {}

        metric_keys = set()
        for run in runs:
            metric_keys.update(run.metrics.keys())

        avg = {}
        for key in metric_keys:
            values = [run.metrics.get(key, 0) for run in runs if key in run.metrics]
            if values:
                avg[key] = sum(values) / len(values)

        return avg

    def _generate_summary(self, runs: list[ExperimentRun]) -> dict[str, Any]:
        """Generate campaign summary statistics."""
        total_runs = len(runs)
        successful_runs = sum(1 for r in runs if r.success)
        failed_runs = total_runs - successful_runs

        # Group by experiment
        experiment_stats = {}
        for run in runs:
            exp_name = run.experiment_name
            if exp_name not in experiment_stats:
                experiment_stats[exp_name] = {"total": 0, "success": 0, "failed": 0}
            experiment_stats[exp_name]["total"] += 1
            if run.success:
                experiment_stats[exp_name]["success"] += 1
            else:
                experiment_stats[exp_name]["failed"] += 1

        # Compute average duration
        durations = [r.duration_seconds for r in runs if r.success]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "success_rate": successful_runs / total_runs if total_runs > 0 else 0,
            "average_duration_seconds": avg_duration,
            "experiment_stats": experiment_stats,
        }


class CheckpointManager:
    """Manager for campaign checkpoint and resume functionality."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.checkpoint_file = output_dir / "campaign_checkpoint.json"

    def save_checkpoint(self, result: CampaignResult) -> None:
        """Save campaign checkpoint."""
        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            import json
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    def load_checkpoint(self) -> CampaignResult | None:
        """Load campaign checkpoint if exists."""
        if not self.checkpoint_file.exists():
            return None

        with open(self.checkpoint_file, "r", encoding="utf-8") as f:
            import json
            data = json.load(f)
            return CampaignResult.from_dict(data)

    def clear_checkpoint(self) -> None:
        """Clear campaign checkpoint."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
