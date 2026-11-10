"""Campaign execution runner for orchestrating multiple experiments."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from ._schema import CampaignConfig, CampaignResult, ExperimentRun
from ..statistics import bootstrap_confidence_interval, paired_bootstrap_difference
from package.config import get_data_paths

import yaml
from statistics import stdev


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

        # Multi-turn plans are resolved once up-front so the campaign policy
        # ("once"/"never"/"all") and per-experiment opt-ins are decided before
        # any run starts.
        mt_plans = self._multi_turn_plans(experiments, output_dir)

        # Execute each experiment
        for exp_idx, experiment in enumerate(experiments):
            for run_num in range(1, experiment.repetition_count + 1):
                run = self._run_experiment(
                    experiment,
                    run_num,
                    output_dir,
                    multi_turn=mt_plans.get((exp_idx, run_num)),
                )
                runs.append(run)

        # Perform comparisons if configured
        comparisons = {}
        if comparison_pairs:
            comparisons = self._run_comparisons(runs, output_dir, comparison_pairs)

        # Generate summary
        summary = self._generate_summary(runs)

        result = CampaignResult(
            campaign_id=self.config.campaign_id,
            campaign_hash=campaign_hash,
            runs=runs,
            comparisons=comparisons,
            summary=summary,
            git_sha=self.git_sha,
            multi_turn=self._collect_multi_turn_result(runs),
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
        multi_turn: dict[str, Any] | None = None,
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
        experiment_dir = ""

        try:
            # Per-experiment tunables go through a CONFIG_OVERLAY_PATH YAML (merged over
            # configs/ by load_config) — run_agent_eval.py itself only takes runtime selectors.
            overlay = self._build_config_overlay(
                experiment, run_number, multi_turn=multi_turn, campaign_dir=output_dir
            )
            overlay_path = exp_output_dir / "config_overlay.yaml"
            overlay_path.write_text(
                yaml.safe_dump(overlay, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )

            # dataset.filters.domains selects the data bundle: run_agent_eval derives
            # the artifact tag from it (one domain -> its name, all/none -> merged_name).
            domains = self.config.dataset.get("filters", {}).get("domains", [])
            cmd = [
                sys.executable,
                "scripts/evaluation/run_agent_eval.py",
                "--eval-on", self.config.dataset.get("split", "validation"),
            ]
            for domain in domains:
                cmd.extend(["--domain", domain])

            # Re-running a campaign reuses the same trajectory file name; resume it
            # (run_agent_eval validates the protocol hash and refuses mismatched logs).
            trajectory_file = overlay["agent/agent_eval"]["agent_eval"]["trajectory_file"]
            traj_path = get_data_paths(domains=domains or None).log_dir / trajectory_file
            if traj_path.exists():
                cmd.append("--resume")

            # Set environment variables
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
                exp_dir = self._experiment_dir_from_stdout(result.stdout)
                experiment_dir = str(exp_dir) if exp_dir is not None else ""
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
            experiment_dir=experiment_dir,
            success=success,
            error=error,
            duration_seconds=duration,
            metrics=metrics,
        )

    # agent_config keys the overlay builder knows how to map; anything else is a config error
    _AGENT_CONFIG_KEYS = {"agents", "inference_mode", "reflect_rounds", "multi_turn"}
    _EVALUATION_CONFIG_KEYS = {"per_segment"}

    # agent_config.multi_turn accepts bool or a dict; these keys map onto
    # agent_eval.multi_turn. output_dir is NOT accepted — the campaign owns
    # artifact placement so campaign_result.json can find every file.
    _MULTI_TURN_PARAM_KEYS = {"enabled", "dataset", "limits", "timeout_seconds"}

    @classmethod
    def _normalize_multi_turn_param(cls, value: Any) -> dict[str, Any]:
        """agent_config.multi_turn -> agent_eval.multi_turn fragment.

        ``True`` -> enabled with base-yaml defaults; ``False``/absent ->
        disabled; a dict may set enabled/dataset/limits/timeout_seconds.
        """
        if value is None or value is False:
            return {"enabled": False}
        if value is True:
            return {"enabled": True}
        if isinstance(value, dict):
            unknown = set(value) - cls._MULTI_TURN_PARAM_KEYS
            if unknown:
                raise ValueError(
                    f"agent_config.multi_turn has unmapped keys {sorted(unknown)}; "
                    f"supported: {sorted(cls._MULTI_TURN_PARAM_KEYS)} "
                    "(output_dir is campaign-controlled)"
                )
            frag = dict(value)
            frag.setdefault("enabled", True)
            return frag if frag["enabled"] else {"enabled": False}
        raise ValueError(
            f"agent_config.multi_turn must be bool or dict, got {type(value).__name__}"
        )

    @staticmethod
    def _multi_turn_run_dir(output_dir: Path, experiment: Any, run_number: int) -> Path:
        return output_dir / "multi_turn" / f"{experiment.name}_run{run_number}"

    def _multi_turn_plans(
        self, experiments: list[Any], output_dir: Path
    ) -> dict[tuple[int, int], dict[str, Any]]:
        """Resolve which runs execute multi-turn and with what config.

        Returns ``{(exp_index, run_number): agent_eval.multi_turn fragment}``.
        Campaign policy (``multi_turn``):

        - ``never`` -> nothing.
        - ``once`` -> at most one run: the first experiment (grid order) that
          opts in via ``agent_config.multi_turn``, first repetition only; if
          NO experiment opts in, the legacy fallback enables experiment[0]
          run 1 so existing configs keep their single multi-turn run.
        - ``all`` -> every run whose experiment opts in (all repetitions).

        Enabled runs write to ``<campaign>/multi_turn/<exp>_run<N>/`` —
        never into an exp_dir.
        """
        mode = getattr(self.config, "multi_turn", "once")
        if mode == "never":
            return {}
        if mode not in ("once", "all"):
            raise ValueError(f"campaign multi_turn must be 'once', 'never' or 'all', got {mode!r}")

        opted: list[tuple[int, int, dict[str, Any]]] = []
        for exp_idx, experiment in enumerate(experiments):
            frag = self._normalize_multi_turn_param(experiment.agent_config.get("multi_turn"))
            for run_num in range(1, experiment.repetition_count + 1):
                if frag.get("enabled"):
                    opted.append((exp_idx, run_num, frag))

        plans: dict[tuple[int, int], dict[str, Any]] = {}
        if mode == "all":
            chosen = opted
        elif opted:
            chosen = opted[:1]
        else:
            # Legacy fallback: preserve the pre-param behaviour — first
            # experiment's first repetition runs multi-turn with defaults.
            chosen = [(0, 1, {"enabled": True})]
        for exp_idx, run_num, frag in chosen:
            experiment = experiments[exp_idx]
            plans[(exp_idx, run_num)] = {
                **frag,
                "output_dir": str(self._multi_turn_run_dir(output_dir, experiment, run_num)),
            }
        return plans

    def _build_config_overlay(
        self,
        experiment: Any,
        run_number: int,
        multi_turn: dict[str, Any] | None = None,
        campaign_dir: Path | None = None,
    ) -> dict[str, Any]:
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
            "campaign_id": self.config.campaign_id,
        }
        per_segment = experiment.evaluation_config.get("per_segment")
        if per_segment is not None:
            agent_eval["per_segment"] = per_segment

        # Multi-turn fragment resolved by _multi_turn_plans; every other run
        # gets enabled=false explicitly so a base-yaml enabled=true cannot
        # leak into the grid.
        agent_eval["multi_turn"] = multi_turn if multi_turn is not None else {"enabled": False}

        overlay: dict[str, Any] = {"agent/agent_eval": {"agent_eval": agent_eval}}

        # Pin artifacts to the run dir itself: run_agent_eval writes
        # config.yaml/metrics.json/trajectories.jsonl into agent_eval.
        # experiment_dir, so campaigns/<id>/<exp>/run_N/ is self-contained.
        if campaign_dir is not None:
            run_dir = campaign_dir / experiment.name / f"run_{run_number}"
            agent_eval["experiment_dir"] = str(run_dir)

            # Fit ItemKNN once per campaign: item_knn_reuse_cache lets the first
            # run save a provenance-validated artifact and siblings load it
            # (data_hash + mapping/split/tag + k + sha256 all checked). The cache
            # lives under the campaign dir — never the shared resource/item_knn
            # pool — so a campaign cannot clobber pipeline artifacts.
            src_root = Path(get_data_paths().src_root)
            knn_root = os.path.relpath(campaign_dir / "item_knn", src_root)
            overlay["path/data_paths"] = {"paths": {"item_knn_dir": Path(knn_root).as_posix()}}
            agent_eval["item_knn_reuse_cache"] = True

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

        # Flatten to get overall averages across all agents/kinds/segments.
        # Skip bookkeeping keys that are not metrics (e.g. "n" = sample count).
        _NON_METRIC_KEYS = {"n"}
        all_metrics = {}
        for agent, kinds in summary.items():
            for kind, segments in kinds.items():
                for segment, metrics in segments.items():
                    if segment == "all":  # Use the aggregated "all" segment
                        for key, value in metrics.items():
                            if key in _NON_METRIC_KEYS:
                                continue
                            if isinstance(value, (int, float)):
                                metric_key = f"{agent}_{kind}_{key}"
                                all_metrics[metric_key] = value

        return all_metrics

    @staticmethod
    def _run_multi_turn_fragment(run: ExperimentRun) -> dict[str, Any] | None:
        """Read the multi_turn block this run's overlay actually applied.

        The overlay file is written before the subprocess starts, so it
        reflects what run_agent_eval saw even when the run failed early.
        """
        ov_path = Path(run.output_dir) / "config_overlay.yaml"
        if not ov_path.exists():
            return None
        try:
            ov = yaml.safe_load(ov_path.read_text(encoding="utf-8")) or {}
            frag = (
                (ov.get("agent/agent_eval") or {}).get("agent_eval") or {}
            ).get("multi_turn")
            return frag if isinstance(frag, dict) else None
        except Exception:
            return None

    def _collect_multi_turn_result(
        self,
        runs: list[ExperimentRun],
    ) -> dict[str, Any]:
        """Summarize every multi_turn artifact for campaign_result.json.

        Each enabled run wrote ``<its output_dir>/multi_turn.json`` where the
        dir comes from that run's own config_overlay.yaml — no copying, one
        artifact per run. Per-run statuses: ``success`` |
        ``skipped_no_credentials`` | ``failed`` | ``error`` | ``timeout`` |
        ``not_run``. Overall ``status``: ``disabled`` (policy never),
        ``not_run`` (nothing enabled/produced), the shared status when all
        runs agree, else ``partial``. Metrics are informational only —
        never fed into comparisons.
        """
        mode = getattr(self.config, "multi_turn", "once")
        if mode == "never":
            return {"status": "disabled", "mode": mode, "runs": []}

        from package.evaluation.multi_turn import extract_multi_turn_metrics

        entries: list[dict[str, Any]] = []
        for run in runs:
            frag = self._run_multi_turn_fragment(run)
            if not frag or not frag.get("enabled"):
                continue
            entry: dict[str, Any] = {
                "experiment": run.experiment_name,
                "run_number": run.run_number,
            }
            out_dir = frag.get("output_dir")
            mt_file = Path(out_dir) / "multi_turn.json" if out_dir else None
            if mt_file is not None and mt_file.exists():
                try:
                    data = json.loads(mt_file.read_text(encoding="utf-8"))
                except Exception as exc:
                    entry.update(status="error", path=str(mt_file), error=str(exc))
                else:
                    status = data.get("status")
                    if status is None and "total_conversations" in data:
                        status = "success"  # summary files predating the status field
                    entry.update(
                        status=status or "unknown",
                        path=str(mt_file),
                        metrics=extract_multi_turn_metrics(data),
                    )
            else:
                if not run.success and run.error:
                    reason = f"run failed before multi-turn step: {run.error[:300]}"
                else:
                    reason = "run completed but produced no multi_turn.json"
                entry.update(status="not_run", reason=reason)
            entries.append(entry)

        if not entries:
            return {
                "status": "not_run",
                "mode": mode,
                "runs": [],
                "reason": "no run had multi_turn enabled",
            }

        statuses = [e["status"] for e in entries]
        if all(s == "success" for s in statuses):
            overall = "success"
        elif len(set(statuses)) == 1:
            overall = statuses[0]
        else:
            overall = "partial"
        return {"status": overall, "mode": mode, "runs": entries}

    def _run_comparisons(
        self,
        runs: list[ExperimentRun],
        output_dir: Path,
        comparison_pairs: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Run comparisons between experiment pairs.

        Args:
            runs: List of experiment runs
            output_dir: Output directory
            comparison_pairs: Pairs to compare; defaults to config.comparison_pairs.
                Callers that auto-generate pairs (parameter grid) MUST pass them here —
                reading self.config.comparison_pairs would silently drop auto-generated pairs.

        Returns:
            Dict of comparison results
        """
        comparisons = {}
        pairs = comparison_pairs if comparison_pairs is not None else self.config.comparison_pairs

        for exp_a, exp_b in pairs:
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

        # statistical_settings from campaign.yaml drives bootstrap CIs.
        # Note: ablation/_statistics.py has a separate bootstrap_ci + McNemar
        # for per-case paired diffs — different semantics (run-level vs
        # case-level pairing); kept separate intentionally.
        stats_cfg = self.config.statistical_settings or {}
        confidence = float(stats_cfg.get("confidence_level", 0.95))
        n_bootstrap = int(stats_cfg.get("bootstrap_samples", 1000))
        paired = bool(stats_cfg.get("paired_comparison", True))
        seed = stats_cfg.get("random_seed")
        comparison["statistics"] = {
            "confidence_level": confidence,
            "bootstrap_samples": n_bootstrap,
            "paired_comparison": paired,
        }

        # Compute deltas
        metric_stats: dict[str, Any] = {}
        for key in set(avg_a.keys()) | set(avg_b.keys()):
            val_a = avg_a.get(key, 0)
            val_b = avg_b.get(key, 0)
            delta_entry: dict[str, Any] = {
                "a": val_a,
                "b": val_b,
                "delta": val_b - val_a,
                "relative_delta": (val_b - val_a) / val_a if val_a != 0 else 0,
            }

            # Per-experiment mean/std/CI across repeated runs + paired delta CI.
            values_a = [r.metrics[key] for r in runs_a if key in r.metrics]
            values_b = [r.metrics[key] for r in runs_b if key in r.metrics]
            if len(values_a) >= 2 or len(values_b) >= 2:
                stat: dict[str, Any] = {}
                for side, values in (("a", values_a), ("b", values_b)):
                    if len(values) >= 2:
                        mean, lo, hi = bootstrap_confidence_interval(
                            values, confidence, n_bootstrap, seed
                        )
                        stat[side] = {
                            "mean": mean,
                            "std": float(stdev(values)),
                            "ci": [lo, hi],
                            "n": len(values),
                        }
                if stat:
                    metric_stats[key] = stat
            if (
                paired
                and len(values_a) >= 2
                and len(values_a) == len(values_b)
            ):
                mean_diff, dlo, dhi, p_value = paired_bootstrap_difference(
                    values_a, values_b, confidence, n_bootstrap, seed
                )
                delta_entry["delta_ci"] = [dlo, dhi]
                delta_entry["p_value"] = p_value
                delta_entry["significant"] = bool(dlo > 0 or dhi < 0)
            comparison["deltas"][key] = delta_entry

        if metric_stats:
            comparison["metric_stats"] = metric_stats

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

