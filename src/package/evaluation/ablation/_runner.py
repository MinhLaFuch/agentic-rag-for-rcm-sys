"""Shared ablation contrast execution.

Used by both `scripts/experiments/compare_experiments.py` (groups resolved
from configs/agent/ablation.yaml paths) and the campaign runner (groups
resolved from experiment names to run directories). One code path, one
artifact layout: <output_dir>/<contrast_name>/{report.md, comparison.json,
comparison.csv, disagreements.jsonl}.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from package.config.load_config import ConfigError

from ._compare import compare_two_groups, find_disagreements, pair_by_request_id
from ._loader import load_group_data_dirs, validate_contrast_config
from ._report import (
    render_markdown_report,
    write_csv,
    write_disagreements,
    write_json,
)


def run_ablation_contrasts(
    *,
    limits: Any,
    groups: dict[str, list[Path]],
    contrasts: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    """Run every contrast and write per-contrast artifacts.

    Args:
        limits: AblationLimits — only metrics/bootstrap_resamples/confidence/
            min_n_warn/seed are read; groups/contrasts/output_subdir are ignored
            (callers supply their own).
        groups: group name -> resolved experiment directories (each must
            contain config.yaml + scored.jsonl)
        contrasts: contrast dicts {name, a: [agent, group], b: [agent, group],
            kinds?: [...]}
        output_dir: directory receiving <contrast_name>/ subdirectories

    Returns:
        {"contrasts": {name: {"status": "ok"|"error", "error"?: str}},
         "missing_columns": [...], "output_dir": str}
        A failing contrast is recorded and the loop continues — one bad
        contrast must not sink the others.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    contrast_status: dict[str, Any] = {}
    missing_columns: set[str] = set()

    for contrast in contrasts:
        name = contrast.get("name", "<unnamed>")
        try:
            validate_contrast_config(contrast, groups)
        except ConfigError as e:
            contrast_status[name] = {"status": "error", "error": str(e)}
            continue

        agent_a, group_a = contrast["a"]
        agent_b, group_b = contrast["b"]
        kinds = contrast.get("kinds")

        try:
            group_data_a = load_group_data_dirs(group_a, groups[group_a])
            group_data_b = load_group_data_dirs(group_b, groups[group_b])
        except ConfigError as e:
            contrast_status[name] = {"status": "error", "error": str(e)}
            continue

        k = group_data_a["configs"][0]["config"]["k"]
        results = compare_two_groups(
            group_data_a, group_data_b, agent_a, agent_b, kinds, k, limits
        )
        if "error" in results:
            contrast_status[name] = {"status": "error", "error": results["error"]}
            continue

        scored_a_flat = [
            r for scored in group_data_a["scored"] for r in scored if r["agent"] == agent_a
        ]
        scored_b_flat = [
            r for scored in group_data_b["scored"] for r in scored if r["agent"] == agent_b
        ]
        pairs = pair_by_request_id(scored_a_flat, scored_b_flat, agent_a, agent_b)
        disagreements = find_disagreements(pairs)

        if results.get("all_kinds"):
            for kind_metrics in results["all_kinds"].values():
                for metric in limits.metrics:
                    metric_formatted = metric.format(k=k) if "{k}" in metric else metric
                    if metric_formatted not in kind_metrics:
                        missing_columns.add(metric_formatted)

        contrast_dir = output_dir / name
        contrast_dir.mkdir(parents=True, exist_ok=True)

        report_md = render_markdown_report(
            results, name, agent_a, agent_b, group_a, group_b, limits, k,
            sorted(missing_columns),
        )
        (contrast_dir / "report.md").write_text(report_md, encoding="utf-8")
        write_json(results, name, agent_a, agent_b, group_a, group_b, limits, k,
                   contrast_dir / "comparison.json")
        write_csv(results, name, agent_a, agent_b, group_a, group_b, limits, k,
                  contrast_dir / "comparison.csv")
        write_disagreements(disagreements, contrast_dir / "disagreements.jsonl")

        contrast_status[name] = {"status": "ok"}

    n_ok = sum(1 for s in contrast_status.values() if s["status"] == "ok")
    return {
        "status": "completed" if n_ok == len(contrast_status) else ("partial" if n_ok else "error"),
        "contrasts": contrast_status,
        "missing_columns": sorted(missing_columns),
        "output_dir": str(output_dir),
    }
