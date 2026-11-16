"""CLI for linking component results with end-to-end results.

Reads an experiment run directory (``scored.jsonl``, ``trajectories.jsonl``,
``metrics.json``, ``config.yaml``) produced by ``run_agent_eval`` and writes:

- ``component_e2e_link.json`` — per-component scores + request-level
  correlation where request IDs overlap.
- ``traceback_analysis.json`` — per-request failure attribution derived from
  ``component_failure_diagnosis`` in scored rows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from package.evaluation.component.create_traceback_tool import create_traceback_tool
from package.evaluation.component.link_component_to_e2e import link_component_to_e2e


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _agent_name(run_dir: Path) -> str | None:
    cfg_path = run_dir / "config.yaml"
    if not cfg_path.exists():
        return None
    try:
        import yaml

        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        # run config is nested under "config"; fall back to top level
        inner = cfg.get("config") if isinstance(cfg.get("config"), dict) else cfg
        agents = inner.get("agents") or inner.get("agent")
        if isinstance(agents, list) and agents:
            return str(agents[0])
        if isinstance(agents, str):
            return agents
        return inner.get("agent_name")
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Link component benchmark results with an e2e run"
    )
    parser.add_argument(
        "--component-dir",
        type=str,
        default=None,
        help="Directory with component benchmark JSONs (default: component_benchmarks output dir)",
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        default=None,
        help="Experiment run dir containing scored.jsonl/trajectories.jsonl/metrics.json",
    )
    parser.add_argument(
        "--e2e-file",
        type=str,
        default=None,
        help="Legacy: path to a JSON file with e2e results (must contain 'scored' rows)",
    )
    args = parser.parse_args()

    if not args.run_dir and not args.e2e_file:
        parser.error("one of --run-dir or --e2e-file is required")

    from package.config import get_data_paths

    output_dir = get_data_paths().output_dir("component_benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)

    component_dir = (
        Path(args.component_dir) if args.component_dir else output_dir
    )

    # Load component results from directory
    component_results: dict[str, str] = {}
    for result_file in component_dir.glob("*_benchmark_*.json"):
        component = result_file.stem.split("_benchmark_")[0]
        component_results[component] = str(result_file)

    # Build e2e payload
    scored_rows: list[dict] = []
    trajectories: list[dict] = []
    metrics: dict = {}
    agent = None
    run_name = None

    if args.run_dir:
        run_dir = Path(args.run_dir)
        scored_rows = _read_jsonl(run_dir / "scored.jsonl")
        trajectories = _read_jsonl(run_dir / "trajectories.jsonl")
        metrics_path = run_dir / "metrics.json"
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        agent = _agent_name(run_dir)
        run_name = run_dir.parent.name or run_dir.name
    else:
        e2e_path = Path(args.e2e_file)
        if not e2e_path.exists():
            raise FileNotFoundError(f"E2E results file not found: {e2e_path}")
        payload = json.loads(e2e_path.read_text(encoding="utf-8"))
        scored_rows = payload.get("scored") or []
        trajectories = payload.get("trajectories") or []
        metrics = payload.get("metrics", {})
        agent = payload.get("agent")
        run_name = payload.get("run")

    e2e_results = {
        "agent": agent,
        "run": run_name,
        "metrics": metrics,
        "scored": scored_rows,
    }

    link_path = output_dir / "component_e2e_link.json"
    link_component_to_e2e(component_results, e2e_results, link_path)

    traceback_path = output_dir / "traceback_analysis.json"
    create_traceback_tool(scored_rows, traceback_path, trajectories=trajectories)

    print("\nDone!")


if __name__ == "__main__":
    main()
