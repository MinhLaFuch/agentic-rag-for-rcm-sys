"""Campaign execution runner for orchestrating multiple experiments."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from ._schema import CampaignConfig, CampaignResult, ExperimentRun
from .._schema import INFERENCE_AGENTS, PLANNER_AGENTS
from ..statistics import bootstrap_confidence_interval, paired_bootstrap_difference
from ..ablation import get_ablation_limits, run_ablation_contrasts
from package.api import build_llm_provider
from package.config import get_data_paths, load_config
from package.config.load_config import ConfigError

import yaml
from statistics import stdev


class CampaignRunner:
    """Runner for executing campaign experiments."""

    def __init__(self, config: CampaignConfig, git_sha: str = ""):
        self.config = config
        self.git_sha = git_sha

    @staticmethod
    def _select_experiments(experiments: list[Any], only: list[str] | None) -> tuple[list[Any], list[str]]:
        """Filter expanded experiments by --only tokens; names/IDs never renumber.

        Each token is ``<n>`` or ``exp_<n>`` matching ``exp_<n>_*`` names, or an
        exact experiment name. Returns (selected, skipped_names). Raises
        ValueError on an unmatched token — never skips silently.
        """
        if only is None:
            return list(experiments), []
        selected: list[Any] = []
        valid = ", ".join(e.name for e in experiments)
        for token in only:
            token = str(token).strip()
            m = re.fullmatch(r"(?:exp_)?(\d+)", token)
            if m:
                prefix = f"exp_{int(m.group(1))}_"
                matches = [e for e in experiments if e.name.startswith(prefix)]
            else:
                matches = [e for e in experiments if e.name == token]
            if not matches:
                raise ValueError(f"--only: no experiment matches {token!r}; valid IDs/names: {valid}")
            for e in matches:
                if e not in selected:
                    selected.append(e)
        skipped = [e.name for e in experiments if e not in selected]
        return selected, skipped

    def _preflight_llm(self, experiments: list[Any]) -> None:
        """Verify the LLM provider once before any experiment subprocess runs.

        Mirrors run_agent_eval's needs_llm rule per experiment: planner agents
        always need the LLM; inference agents need it when the effective
        inference mode is 'llm' (agent_config overrides the base
        configs/agent/inference.yaml mode). Only selected (--only) experiments
        are checked. Raises SystemExit with an actionable message on failure.
        Set CAMPAIGN_SKIP_LLM_PREFLIGHT=1 to bypass (used by tests).
        """
        if os.environ.get("CAMPAIGN_SKIP_LLM_PREFLIGHT"):
            return
        base_mode = (load_config("agent/inference").get("inference") or {}).get("mode", "template")
        needing: list[str] = []
        for exp in experiments:
            agent_config = {**self.config.agent_config_defaults, **exp.agent_config}
            agents = agent_config.get("agents", list(self.config.default_agents))
            mode = agent_config.get("inference_mode") or base_mode
            if any(a in PLANNER_AGENTS for a in agents) or (
                mode == "llm" and any(a in INFERENCE_AGENTS for a in agents)
            ):
                needing.append(exp.name)
        if not needing:
            return

        detail = ""
        try:
            llm_cfg = load_config("agent/llm")
            llm = build_llm_provider(llm_cfg)
            ok = llm.health_check()
        except Exception as exc:  # missing base_url/model, HTTP error, timeout...
            ok = False
            detail = f" ({exc})"
        if not ok:
            raise SystemExit(
                f"LLM preflight failed{detail}: {len(needing)}/{len(experiments)} selected "
                f"experiments need the LLM (e.g. {needing[0]}). Check LLM_BASE_URL/LLM_API_KEY "
                "env vars and configs/agent/llm.yaml, or restrict the run to offline "
                "experiments (baseline/type1 + inference.mode=template)."
            )
        print(
            f"LLM preflight OK: model={llm_cfg.get('model')} base_url={llm_cfg.get('base_url')} "
            f"({len(needing)}/{len(experiments)} experiments need it)"
        )

    def _preflight_jev(self, experiments: list[Any]) -> None:
        """Warn up-front when Jev is enabled but no judge credential exists.

        Jev is auxiliary (coverage-only, never in comparisons, per-answer
        failures are recorded inside jev_eval.jsonl), so a missing key warns
        instead of aborting the campaign — every run would otherwise only
        discover ``skipped_no_credentials`` after finishing.
        """
        if os.environ.get("CAMPAIGN_SKIP_LLM_PREFLIGHT"):
            return
        enabled = [
            exp.name
            for exp in experiments
            if self._normalize_jev_param(
                {**self.config.agent_config_defaults, **exp.agent_config}.get("jev")
            ).get("enabled")
        ]
        if not enabled:
            return
        from package.evaluation.judge import jev_credentials_configured

        if jev_credentials_configured():
            print(f"Jev preflight OK: credentials found ({len(enabled)}/{len(experiments)} experiments enabled)")
        else:
            print(
                f"WARNING: Jev enabled for {len(enabled)}/{len(experiments)} experiments "
                f"(e.g. {enabled[0]}) but no judge credential — every run will record "
                "skipped_no_credentials. Set JEV_API_KEY (or TYPESAFE_API_KEY / "
                "OPENROUTER_API_KEY), or disable agent_config.jev."
            )

    def run_campaign(self, only: list[str] | None = None) -> CampaignResult:
        """Execute the full campaign.

        Args:
            only: optional list of experiment selectors (``7``, ``exp_7`` or an
                exact experiment name). When given, ONLY those experiments run;
                skipped experiments keep their previous campaign_result.json
                entries untouched, comparisons are not recomputed, and the
                previous result file is merged + backed up before overwrite.

        Returns:
            CampaignResult with all experiment runs and comparisons
        """
        campaign_hash = self.config.compute_hash()

        # Expand parameter grid if provided
        all_experiments = self.config.expand_parameter_grid()

        if not all_experiments:
            raise ValueError("No experiments to run. Either provide 'experiments' list or 'parameter_grid' in campaign config.")

        experiments, skipped_names = self._select_experiments(all_experiments, only)

        # Fail fast: when any selected experiment needs the LLM, verify the
        # provider once up-front instead of dying inside the Nth subprocess.
        self._preflight_llm(experiments)
        self._preflight_jev(experiments)

        print(f"\n=== Campaign Summary ===")
        print(f"Total experiments: {len(all_experiments)}")
        for exp in experiments:
            print(f"  - {exp.name}: {exp.description}")
        if only is not None:
            print(f"Subset run (--only): {len(experiments)} of {len(all_experiments)} experiments")
            for name in skipped_names:
                print(f"  - SKIPPED {name}")

        # Auto-generate comparison pairs if empty and using parameter grid.
        # Pairs are resolved over ALL experiments (not just the --only subset)
        # so a subset merge can recompute comparisons over the merged runs.
        comparison_pairs = self.config.comparison_pairs
        if not comparison_pairs and self.config.parameter_grid:
            # Compare all experiments against the first one (baseline)
            baseline_exp = all_experiments[0]
            comparison_pairs = [(baseline_exp.name, exp.name) for exp in all_experiments[1:]]
            if only is None:
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

        # Perform comparisons if configured (skipped entirely on subset runs)
        comparisons = {}
        if only is None and comparison_pairs:
            comparisons = self._run_comparisons(runs, output_dir, comparison_pairs)

        # Post-run ablation contrasts (full runs only; a subset run cannot
        # resolve both sides of every contrast, and the previous result's
        # ablation block is preserved by _merge_subset_result).
        ablation_result: dict[str, Any] = {}
        if only is None:
            ablation_result = self._run_ablation(runs, output_dir)

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
            ablation=ablation_result,
        )
        if only is not None:
            result.subset = {
                "only": [str(t) for t in only],
                "ran": [e.name for e in experiments],
                "skipped": skipped_names,
                "comparisons": "recomputed_over_merged_runs",
            }

        # Save campaign result
        result_path = output_dir / "campaign_result.json"
        if only is not None:
            result = self._merge_subset_result(
                result, result_path, comparison_pairs=comparison_pairs, output_dir=output_dir
            )
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

        return result

    def _merge_subset_result(
        self,
        result: CampaignResult,
        result_path: Path,
        comparison_pairs: list[tuple[str, str]] | None = None,
        output_dir: Path | None = None,
    ) -> CampaignResult:
        """Merge a subset run into the existing campaign_result.json.

        Runs of skipped experiments keep their previous entries verbatim.
        Comparisons and ablation contrasts are RECOMPUTED over the merged run
        set — preserving the previous blocks would keep metrics computed
        without the re-run experiment's data (the timeout-resume scenario).
        The previous file is backed up first.
        """
        if not result_path.exists():
            return result
        try:
            prev = CampaignResult.from_dict(json.loads(result_path.read_text(encoding="utf-8")))
        except Exception:
            return result

        backup = result_path.with_name(
            f"campaign_result_backup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        shutil.copyfile(result_path, backup)
        print(f"Backed up previous campaign_result.json -> {backup.name}")

        new_runs = {(r.experiment_name, r.run_number): r for r in result.runs}
        merged: list[ExperimentRun] = []
        for r in prev.runs:
            merged.append(new_runs.pop((r.experiment_name, r.run_number), r))
        merged.extend(new_runs.values())  # runs with no previous entry (shouldn't happen for same campaign)

        result.runs = merged
        if comparison_pairs:
            result.comparisons = self._run_comparisons(merged, output_dir, comparison_pairs)
        elif prev.comparisons:
            result.comparisons = prev.comparisons
        result.summary = self._generate_summary(merged)
        result.multi_turn = self._collect_multi_turn_result(merged)
        # Ablation contrasts resolve experiment names to run dirs; merged runs
        # carry experiment_dir for both old and new entries, so recompute gives
        # statuses consistent with the merged run set.
        result.ablation = self._run_ablation(merged, output_dir) if output_dir is not None else prev.ablation
        return result

    def _run_ablation(self, runs: list[ExperimentRun], output_dir: Path) -> dict[str, Any]:
        """Run configured ablation contrasts over this campaign's run dirs.

        Contrasts in campaign.yaml reference experiment NAMES in the a/b
        group slot; each name resolves to the experiment_dir of every
        successful run (repetitions become group members, averaged inside
        compare_two_groups). Metrics/bootstrap parameters still come from
        configs/agent/ablation.yaml — the campaign only says who to compare.
        Returns {"status": "disabled"} when no contrasts are configured.
        """
        contrasts = (self.config.ablation or {}).get("contrasts") or []
        if not contrasts:
            return {"status": "disabled"}
        try:
            limits = get_ablation_limits()
        except ConfigError as e:
            return {"status": "error", "error": str(e)}

        groups: dict[str, list[Path]] = {}
        for run in runs:
            if run.success and run.experiment_dir:
                groups.setdefault(run.experiment_name, []).append(Path(run.experiment_dir))

        summary = run_ablation_contrasts(
            limits=limits,
            groups=groups,
            contrasts=contrasts,
            output_dir=output_dir / "ablation",
        )
        print(f"\nAblation: {summary['status']} -> {summary['output_dir']}")
        for name, st in summary["contrasts"].items():
            suffix = "" if st["status"] == "ok" else f" ({st.get('error')})"
            print(f"  {name}: {st['status']}{suffix}")
        return summary

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
            git_sha=self.git_sha,
        )

    # agent_config keys the overlay builder knows how to map; anything else is a config error
    _AGENT_CONFIG_KEYS = {"agents", "inference_mode", "reflect_rounds", "multi_turn", "exclude_tools", "jev"}
    _EVALUATION_CONFIG_KEYS = {"per_segment", "request_scope"}

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

    # agent_config.jev accepts bool or a dict; these keys map onto
    # agent_eval.jev. The artifact always lands in the experiment dir —
    # the campaign owns artifact placement like multi_turn.
    _JEV_PARAM_KEYS = {"enabled", "max_requests"}

    @classmethod
    def _normalize_jev_param(cls, value: Any) -> dict[str, Any]:
        """agent_config.jev -> agent_eval.jev fragment.

        ``True`` -> enabled with base-yaml defaults; ``False``/absent ->
        disabled; a dict may set enabled/max_requests.
        """
        if value is None or value is False:
            return {"enabled": False}
        if value is True:
            return {"enabled": True}
        if isinstance(value, dict):
            unknown = set(value) - cls._JEV_PARAM_KEYS
            if unknown:
                raise ValueError(
                    f"agent_config.jev has unmapped keys {sorted(unknown)}; "
                    f"supported: {sorted(cls._JEV_PARAM_KEYS)}"
                )
            frag = dict(value)
            frag.setdefault("enabled", True)
            return frag if frag["enabled"] else {"enabled": False}
        raise ValueError(
            f"agent_config.jev must be bool or dict, got {type(value).__name__}"
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
            agent_config = {**self.config.agent_config_defaults, **experiment.agent_config}
            frag = self._normalize_multi_turn_param(agent_config.get("multi_turn"))
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
        # Campaign-level agent_config defaults apply to every experiment;
        # the experiment's own keys win on conflict.
        agent_config = {**self.config.agent_config_defaults, **experiment.agent_config}
        unknown_agent = set(agent_config) - self._AGENT_CONFIG_KEYS
        unknown_eval = set(experiment.evaluation_config) - self._EVALUATION_CONFIG_KEYS
        if unknown_agent or unknown_eval:
            raise ValueError(
                f"Experiment '{experiment.name}' has unmapped config keys: "
                f"agent_config={sorted(unknown_agent)}, evaluation_config={sorted(unknown_eval)}. "
                f"Supported: agent_config={sorted(self._AGENT_CONFIG_KEYS)}, "
                f"evaluation_config={sorted(self._EVALUATION_CONFIG_KEYS)}"
            )

        agent_eval: dict[str, Any] = {
            "agents": agent_config.get("agents", list(self.config.default_agents)),
            "allow_missing_corpus_sources": self.config.allow_missing_corpus_sources,
            "trajectory_file": f"{self.config.campaign_id}_{experiment.name}_run{run_number}_trajectories.jsonl",
            "campaign_id": self.config.campaign_id,
        }
        per_segment = experiment.evaluation_config.get("per_segment")
        if per_segment is not None:
            agent_eval["per_segment"] = per_segment

        request_scope = experiment.evaluation_config.get("request_scope")
        if request_scope is not None:
            agent_eval["request_scope"] = request_scope

        # Multi-turn fragment resolved by _multi_turn_plans; every other run
        # gets enabled=false explicitly so a base-yaml enabled=true cannot
        # leak into the grid.
        agent_eval["multi_turn"] = multi_turn if multi_turn is not None else {"enabled": False}

        # Same leak guard as multi_turn: every run gets an explicit jev fragment
        # so a base-yaml enabled=true cannot leak into the grid.
        agent_eval["jev"] = self._normalize_jev_param(agent_config.get("jev"))

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

        inference_mode = agent_config.get("inference_mode")
        if inference_mode is not None:
            overlay["agent/inference"] = {"inference": {"mode": inference_mode}}

        reflect_rounds = agent_config.get("reflect_rounds")
        if reflect_rounds is not None:
            overlay["agent/agent"] = {"agent": {"reflect_rounds": reflect_rounds}}

        exclude_tools = agent_config.get("exclude_tools")
        if exclude_tools is not None:
            agent_eval["exclude_tools"] = list(exclude_tools)

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

