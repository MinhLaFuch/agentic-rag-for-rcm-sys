"""Campaign execution runner for orchestrating multiple experiments."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from ._schema import CampaignConfig, CampaignResult, ExperimentRun
from package.config import get_data_paths

import yaml


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

        # Expand parameter grid if provided
        experiments = self.config.expand_parameter_grid()

        if not experiments:
            raise ValueError("No experiments to run. Either provide 'experiments' list or 'parameter_grid' in campaign config.")

        print(f"\n=== Campaign Summary ===")
        print(f"Total experiments: {len(experiments)}")
        for exp in experiments:
            print(f"  - {exp.name}: {exp.description}")

        # Auto-generate comparison pairs if empty and using parameter grid
        comparison_pairs = self.config.comparison_pairs
        if not comparison_pairs and self.config.parameter_grid:
            # Compare all experiments against the first one (baseline)
            baseline_exp = experiments[0]
            comparison_pairs = [(baseline_exp.name, exp.name) for exp in experiments[1:]]
            print(f"\nAuto-generated {len(comparison_pairs)} comparison pairs (vs baseline)")

        runs: list[ExperimentRun] = []

        # Create output directory. Relative paths resolve against experiments_dir
        # (experiments/), never the process CWD — see configs/path/data_paths.yaml.
        output_dir = Path(self.config.output_dir)
        if not output_dir.is_absolute():
            output_dir = get_data_paths().experiments_dir / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # Execute each experiment
        for experiment in experiments:
            for run_num in range(1, experiment.repetition_count + 1):
                run = self._run_experiment(experiment, run_num, output_dir)
                runs.append(run)

        # Perform comparisons if configured
        comparisons = {}
        if comparison_pairs:
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
        """Run a single experiment by calling run_agent_eval.py.

        Args:
            experiment: ExperimentConfig
            run_number: Repetition number
            output_dir: Campaign output directory

        Returns:
            ExperimentRun
        """
        exp_output_dir = output_dir / experiment.name / f"run_{run_number}"
        exp_output_dir.mkdir(parents=True, exist_ok=True)

        start_time = datetime.now(timezone.utc)
        success = True
        error = None
        metrics = {}

        try:
            # Per-experiment tunables go through a CONFIG_OVERLAY_PATH YAML (merged over
            # configs/ by load_config) — run_agent_eval.py itself only takes runtime selectors.
            overlay = self._build_config_overlay(experiment, run_number)
            overlay_path = exp_output_dir / "config_overlay.yaml"
            overlay_path.write_text(
                yaml.safe_dump(overlay, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )

            tag = self.config.dataset.get("tag", "default")
            cmd = [
                sys.executable,
                "scripts/evaluation/run_agent_eval.py",
                "--tag", tag,
                "--eval-on", self.config.dataset.get("split", "validation"),
            ]

            # Add domain filters if specified
            domains = self.config.dataset.get("filters", {}).get("domains", [])
            for domain in domains:
                cmd.extend(["--domain", domain])

            # Re-running a campaign reuses the same trajectory file name; resume it
            # (run_agent_eval validates the protocol hash and refuses mismatched logs).
            trajectory_file = overlay["agent/agent_eval"]["agent_eval"]["trajectory_file"]
            traj_path = get_data_paths(tag).log_dir / trajectory_file
            if traj_path.exists():
                cmd.append("--resume")

            # Set environment variables
            from package.config import get_data_paths
            env = dict(subprocess.os.environ)
            env["PYTHONPATH"] = str(get_data_paths().src_root)
            env["CONFIG_OVERLAY_PATH"] = str(overlay_path)

            # Run the script
            print(f"\n=== Running {experiment.name} (run {run_number}) ===")
            print(f"Command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=str(get_data_paths().src_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.config.experiment_timeout_seconds,
            )

            # Check output
            if result.returncode != 0:
                success = False
                error = f"Script failed with return code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                print(error)
            else:
                print(result.stdout)
                # run_agent_eval prints "saved -> <exp_dir>"; that is the deterministic handoff
                metrics = self._load_experiment_metrics(result.stdout)

        except subprocess.TimeoutExpired:
            success = False
            error = f"Experiment timed out after {self.config.experiment_timeout_seconds} seconds"
        except Exception as e:
            success = False
            error = str(e)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        return ExperimentRun(
            experiment_name=experiment.name,
            run_number=run_number,
            output_dir=str(exp_output_dir),
            success=success,
            error=error,
            duration_seconds=duration,
            metrics=metrics,
        )

    # agent_config keys the overlay builder knows how to map; anything else is a config error
    _AGENT_CONFIG_KEYS = {"agents", "inference_mode", "reflect_rounds"}
    _EVALUATION_CONFIG_KEYS = {"per_segment"}

    def _build_config_overlay(self, experiment: Any, run_number: int) -> dict[str, Any]:
        """Build a CONFIG_OVERLAY_PATH YAML fragment for one experiment run.

        Shape mirrors configs/: top-level keys are config names, values are the
        file's own content (e.g. ``agent/agent_eval`` → ``{agent_eval: {...}}``).
        Raises ValueError on agent_config/evaluation_config keys that have no
        mapping — silently dropping them would run the wrong experiment.
        """
        unknown_agent = set(experiment.agent_config) - self._AGENT_CONFIG_KEYS
        unknown_eval = set(experiment.evaluation_config) - self._EVALUATION_CONFIG_KEYS
        if unknown_agent or unknown_eval:
            raise ValueError(
                f"Experiment '{experiment.name}' has unmapped config keys: "
                f"agent_config={sorted(unknown_agent)}, evaluation_config={sorted(unknown_eval)}. "
                f"Supported: agent_config={sorted(self._AGENT_CONFIG_KEYS)}, "
                f"evaluation_config={sorted(self._EVALUATION_CONFIG_KEYS)}"
            )

        agent_eval: dict[str, Any] = {
            "agents": experiment.agent_config.get("agents", list(self.config.default_agents)),
            "allow_missing_corpus_sources": self.config.allow_missing_corpus_sources,
            "trajectory_file": f"{self.config.campaign_id}_{experiment.name}_run{run_number}_trajectories.jsonl",
        }
        per_segment = experiment.evaluation_config.get("per_segment")
        if per_segment is not None:
            agent_eval["per_segment"] = per_segment

        overlay: dict[str, Any] = {"agent/agent_eval": {"agent_eval": agent_eval}}

        inference_mode = experiment.agent_config.get("inference_mode")
        if inference_mode is not None:
            overlay["agent/inference"] = {"inference": {"mode": inference_mode}}

        reflect_rounds = experiment.agent_config.get("reflect_rounds")
        if reflect_rounds is not None:
            overlay["agent/agent"] = {"agent": {"reflect_rounds": reflect_rounds}}

        # experiment.random_seed drives request sampling via eval/baselines.baselines.seed
        overlay["eval/baselines"] = {"baselines": {"seed": experiment.random_seed}}

        return overlay

    @staticmethod
    def _experiment_dir_from_stdout(stdout: str) -> Path | None:
        """Parse the ``saved -> <exp_dir>`` line run_agent_eval.py prints at the end."""
        matches = re.findall(r"saved -> (.+)", stdout)
        if not matches:
            return None
        path = Path(matches[-1].strip())
        if not path.is_absolute():
            path = Path(__file__).parent.parent.parent.parent / path
        return path

    def _load_experiment_metrics(self, stdout: str) -> dict[str, Any]:
        """Load metrics from the experiment dir reported by run_agent_eval stdout.

        Args:
            stdout: Captured stdout of the run_agent_eval.py subprocess

        Returns:
            Dict with aggregated metrics from metrics.json
        """
        exp_dir = self._experiment_dir_from_stdout(stdout)
        if exp_dir is None:
            return {}

        metrics_file = exp_dir / "metrics.json"
        if not metrics_file.exists():
            return {}

        with open(metrics_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extract summary metrics from the data
        # metrics.json = save_experiment(metrics=...) = {"k": 10, "summary": {agent: {kind: {segment: {...}}}}}
        summary = data.get("summary", data.get("metrics", {}).get("summary", {}))

        # Flatten to get overall averages across all agents/kinds/segments
        all_metrics = {}
        for agent, kinds in summary.items():
            for kind, segments in kinds.items():
                for segment, metrics in segments.items():
                    if segment == "all":  # Use the aggregated "all" segment
                        for key, value in metrics.items():
                            if isinstance(value, (int, float)):
                                metric_key = f"{agent}_{kind}_{key}"
                                all_metrics[metric_key] = value

        return all_metrics

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

