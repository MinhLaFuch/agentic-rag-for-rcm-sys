"""
So sánh thí nghiệm ablation (base template).

Cách chạy:
    PYTHONPATH=. python scripts/experiments/compare_experiments.py

Đọc config từ configs/agent/ablation.yaml, load dữ liệu từ các exp_NNN directories,
so sánh theo các contrast được định nghĩa, và sinh báo cáo markdown/CSV/JSON.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from package.agents.ablation._compare import (
    compare_two_groups,
    find_disagreements,
    pair_by_request_id,
)
from package.agents.ablation._limits import get_ablation_limits
from package.agents.ablation._loader import (
    load_group_data,
    validate_contrast_config,
)
from package.agents.ablation._report import (
    render_markdown_report,
    write_csv,
    write_disagreements,
    write_json,
)
from package.config import get_data_paths
from package.config.load_config import ConfigError
from package.utils.console import ensure_utf8_stdout


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Compare ablation experiments")
    ap.add_argument("--config", default="agent/ablation", help="Config file path (default: agent/ablation)")
    return ap.parse_args()


def main() -> None:
    ensure_utf8_stdout()
    args = parse_args()
    
    print("=" * 60)
    print("Ablation Comparison Tool")
    print("=" * 60)
    
    # Load limits
    print(f"Loading config from configs/{args.config}.yaml...")
    try:
        limits = get_ablation_limits()
    except ConfigError as e:
        print(f"ERROR: {e}")
        return
    
    print(f"Bootstrap resamples: {limits.bootstrap_resamples}")
    print(f"Confidence: {limits.confidence}")
    print(f"Min n warn: {limits.min_n_warn}")
    print(f"Seed: {limits.seed}")
    print(f"Metrics: {', '.join(limits.metrics)}")
    print(f"Groups: {list(limits.groups.keys())}")
    print(f"Contrasts: {len(limits.contrasts)}")
    print("")
    
    # Validate groups exist
    for group_name, exp_names in limits.groups.items():
        print(f"Validating group '{group_name}' with exps: {exp_names}")
        try:
            load_group_data(group_name, exp_names)
        except ConfigError as e:
            print(f"ERROR loading group '{group_name}': {e}")
            return
    print("")
    
    # Prepare output directory
    data_paths = get_data_paths()
    output_dir = data_paths.experiments_dir / limits.output_subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run each contrast
    all_results = {}
    missing_columns = set()
    
    for contrast in limits.contrasts:
        print(f"\nProcessing contrast: {contrast['name']}")
        
        # Validate contrast
        try:
            validate_contrast_config(contrast, limits.groups)
        except ConfigError as e:
            print(f"ERROR in contrast '{contrast['name']}': {e}")
            continue
        
        agent_a, group_a = contrast["a"]
        agent_b, group_b = contrast["b"]
        kinds = contrast.get("kinds")
        
        print(f"  A: {agent_a} (group: {group_a})")
        print(f"  B: {agent_b} (group: {group_b})")
        if kinds:
            print(f"  Kinds: {kinds}")
        
        # Load group data
        try:
            group_data_a = load_group_data(group_a, limits.groups[group_a])
            group_data_b = load_group_data(group_b, limits.groups[group_b])
        except ConfigError as e:
            print(f"ERROR loading groups: {e}")
            continue
        
        # Get k from config
        k = group_data_a["configs"][0]["config"]["k"]
        
        # Compare
        results = compare_two_groups(
            group_data_a,
            group_data_b,
            agent_a,
            agent_b,
            kinds,
            k,
            limits,
        )
        
        if "error" in results:
            print(f"  ERROR: {results['error']}")
            all_results[contrast["name"]] = results
            continue
        
        # Find disagreements
        scored_a_flat = [r for scored in group_data_a["scored"] for r in scored if r["agent"] == agent_a]
        scored_b_flat = [r for scored in group_data_b["scored"] for r in scored if r["agent"] == agent_b]
        pairs = pair_by_request_id(scored_a_flat, scored_b_flat, agent_a, agent_b)
        disagreements = find_disagreements(pairs)
        
        # Track missing columns
        if results.get("all_kinds"):
            for kind_metrics in results["all_kinds"].values():
                for metric in limits.metrics:
                    metric_formatted = metric.format(k=k) if "{k}" in metric else metric
                    if metric_formatted not in kind_metrics:
                        missing_columns.add(metric_formatted)
        
        # Write outputs
        contrast_output_dir = output_dir / contrast["name"]
        contrast_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Markdown report
        report_md = render_markdown_report(
            results,
            contrast["name"],
            agent_a,
            agent_b,
            group_a,
            group_b,
            limits,
            k,
            sorted(missing_columns),
        )
        report_path = contrast_output_dir / "report.md"
        report_path.write_text(report_md, encoding="utf-8")
        print(f"  Saved report: {report_path}")
        
        # JSON
        json_path = contrast_output_dir / "comparison.json"
        write_json(results, contrast["name"], agent_a, agent_b, group_a, group_b, limits, k, json_path)
        print(f"  Saved JSON: {json_path}")
        
        # CSV
        csv_path = contrast_output_dir / "comparison.csv"
        write_csv(results, contrast["name"], agent_a, agent_b, group_a, group_b, limits, k, csv_path)
        print(f"  Saved CSV: {csv_path}")
        
        # Disagreements
        disagreements_path = contrast_output_dir / "disagreements.jsonl"
        write_disagreements(disagreements, disagreements_path)
        print(f"  Saved disagreements: {disagreements_path} ({len(disagreements)} entries)")
        
        all_results[contrast["name"]] = results
    
    # Write summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Output directory: {output_dir}")
    print(f"Contrasts processed: {len(all_results)}")
    
    if missing_columns:
        print(f"\nMissing columns (skipped): {', '.join(sorted(missing_columns))}")
    
    print("\nDone.")


if __name__ == "__main__":
    main()
