"""Paired Vietnamese runtime validation; no test-split tuning or automatic promotion."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml


def prepare(output: Path, per_segment: int, scope: str) -> list[tuple[str, Path]]:
    repo = Path(__file__).resolve().parents[3]
    base = repo / "src/configs/profiles/multi_domain_v2_audit_20261030.runtime_winning.overlay.yaml"
    arms = []
    for name, retrieval, scorer in [
        ("lexical_baseline", "bm25", "baseline"),
        ("hybrid_baseline", "hybrid", "baseline"),
        ("hybrid_w4", "hybrid", "hybrid"),
    ]:
        overlay = yaml.safe_load(base.read_text(encoding="utf-8"))
        overlay["agent/demo"]["demo"].update(
            retrieval_mode=retrieval, fallback_to_bm25=False, translate_vietnamese=True,
        )
        overlay["eval/dense_retrieval"] = {"dense_retrieval": {"enabled": False}}
        overlay["agent/scoring"] = {"scoring": {"mode": scorer, "hybrid_popularity_weight": 4.0}}
        overlay["agent/agent_eval"] = {"agent_eval": {
            "agents": ["planner_memory"], "language": "vi", "per_segment": per_segment,
            "request_scope": scope, "experiment_dir": str(output / name),
            "trajectory_file": "trajectories.jsonl", "enable_session": False,
            "metadata_policy": "historical_static_catalog", "allow_missing_corpus_sources": False,
            "multi_turn": {"enabled": False}, "jev": {"enabled": False},
        }}
        overlay["agent/agent"] = {"agent": {"reflect_rounds": 0}}
        overlay["agent/inference"] = {"inference": {"mode": "llm"}}
        path = output / f"{name}.overlay.yaml"
        content = yaml.safe_dump(overlay, allow_unicode=True, sort_keys=False)
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise ValueError(f"Existing experiment config differs: {path}; choose a new output")
        path.write_text(content, encoding="utf-8")
        arms.append((name, path))
    return arms


def runtime_environment(repo: Path, overlay: Path) -> dict[str, str]:
    """Keep the immutable audit overlay first and the arm-specific overrides last."""
    env = dict(os.environ, PYTHONPATH=str(repo / "src"))
    profiles = repo / "src/configs/profiles"
    env["EVAL_BUNDLE_PROFILE"] = str((profiles / "multi_domain_v2_audit_20261030.profile.yaml").resolve())
    audit_overlay = (profiles / "multi_domain_v2_audit_20261030.overlay.yaml").resolve()
    env["CONFIG_OVERLAY_PATH"] = os.pathsep.join([str(audit_overlay), str(overlay.resolve())])
    return env


def check_llm(config: dict) -> None:
    """Fail before dataset loading, without printing credentials."""
    if not str(config.get("base_url") or "").strip() or not str(config.get("model") or "").strip():
        raise ValueError(
            "LLM is not configured: set LLM_BASE_URL in this PowerShell session "
            "and a non-empty model in configs/agent/llm.yaml. "
            "Set LLM_API_KEY if your endpoint requires authentication."
        )
    from package.api import build_llm_provider
    if not build_llm_provider(config).health_check():
        raise RuntimeError(
            "LLM health check failed before dataset loading; check endpoint, model and authentication."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-segment", type=int, default=20)
    parser.add_argument("--scope", choices=["realistic", "all"], default="realistic")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.per_segment <= 0:
        parser.error("--per-segment must be positive")
    repo = Path(__file__).resolve().parents[3]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    arms = prepare(output, args.per_segment, args.scope)
    # Validate generated overlays before any model loading or paid LLM call.
    from package.config import get_data_paths, load_config
    from package.data.manifest.load_audit_profile import load_audit_profile
    saved_env = {key: os.environ.get(key) for key in ("CONFIG_OVERLAY_PATH", "EVAL_BUNDLE_PROFILE")}
    try:
        for _, path in arms:
            arm_env = runtime_environment(repo, path)
            for key in saved_env:
                os.environ[key] = arm_env[key]
            for key in yaml.safe_load(path.read_text(encoding="utf-8")):
                load_config(key)
            load_audit_profile(get_data_paths())
        if not args.prepare_only:
            check_llm(load_config("agent/llm"))
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    print(f"Prepared: {output}", flush=True)
    if args.prepare_only:
        return
    for name, overlay in arms:
        env = runtime_environment(repo, overlay)
        cmd = [sys.executable, "-u", "-c", "import torch, faiss, runpy; runpy.run_module('scripts.evaluation.run_agent_eval', run_name='__main__')", "--eval-on", "validation"]
        if args.resume:
            cmd.append("--resume")
        print(f"Running {name}", flush=True)
        subprocess.run(cmd, cwd=repo, env=env, check=True)
    # Require identical requests AND targets before interpreting paired differences.
    cohorts = []
    for name, _ in arms:
        records = [json.loads(line) for line in (output / name / "requests.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if not records:
            raise ValueError(f"Empty request cohort: {name}")
        cohorts.append(sorted(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records))
    if any(c != cohorts[0] for c in cohorts[1:]):
        raise ValueError("Request cohort mismatch; paired comparison refused")
    for a, b in [("lexical_baseline", "hybrid_baseline"), ("hybrid_baseline", "hybrid_w4")]:
        subprocess.run([
            sys.executable, "-m", "scripts.experiments.pairwise_ablation",
            "--a", str(output / a / "scored.jsonl"), "--a-agent", "planner_memory",
            "--b", str(output / b / "scored.jsonl"), "--b-agent", "planner_memory",
            "--out", str(output / f"{a}_vs_{b}.md"),
            "--json-out", str(output / f"{a}_vs_{b}.json"),
        ], cwd=repo, env=env, check=True)
    print(f"Completed validation A/B: {output}")


if __name__ == "__main__":
    main()
