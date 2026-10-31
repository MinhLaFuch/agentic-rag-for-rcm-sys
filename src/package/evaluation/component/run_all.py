"""Run all component benchmarks and generate unified report."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from package.config import get_data_paths


def run_all_benchmarks(
    runs: int = 1,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Run all component benchmarks and collect results."""
    if output_dir is None:
        output_dir = Path.cwd() / "benchmark_results"
    output_dir.mkdir(exist_ok=True)

    components = [
        ("memory", "package/evaluation/component/benchmarks/memory_correctness_dataset.jsonl"),
        ("planner", "package/evaluation/component/benchmarks/planner_dataset.jsonl"),
        ("executor", "package/evaluation/component/benchmarks/executor_dataset.jsonl"),
        ("grounding", "package/evaluation/component/benchmarks/grounding_dataset.jsonl"),
        ("integration", "package/evaluation/component/benchmarks/integration_dataset.jsonl"),
    ]

    results = {}

    for component, dataset in components:
        print(f"\n{'='*60}")
        print(f"Running {component} benchmark...")
        print(f"{'='*60}")

        try:
            # Run benchmark from src directory
            cmd = [
                sys.executable, "-m", "package.evaluation.component.run",
                "--component", component,
                "--dataset", dataset,
                "--runs", str(runs),
            ]
            
            # Add config files if they exist
            if component == "planner":
                cmd.extend(["--config", "planner_llm_config.json"])
            elif component == "executor":
                cmd.extend(["--config", "executor_reflection_config.json"])
            elif component == "grounding":
                cmd.extend(["--config", "grounding_jev_config.json"])

            # Run from src directory
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=str(Path(__file__).parent.parent.parent.parent))
            print(result.stdout)

            # Extract result file path from output
            for line in result.stdout.split('\n'):
                if "Results saved to:" in line:
                    result_file = line.split("Results saved to:")[-1].strip()
                    results[component] = str(Path(__file__).parent.parent.parent.parent / result_file)
                    break

        except subprocess.CalledProcessError as e:
            print(f"Error running {component}: {e}")
            print(f"stderr: {e.stderr}")
            results[component] = None

    return results


def aggregate_results(result_files: dict[str, str | None]) -> dict[str, Any]:
    """Aggregate all benchmark results into unified report."""
    aggregated = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {},
        "summary": {
            "total_components": len(result_files),
            "successful_components": 0,
            "failed_components": 0,
        },
    }

    for component, result_file in result_files.items():
        if result_file is None:
            aggregated["components"][component] = {"status": "failed", "error": "Benchmark did not run"}
            aggregated["summary"]["failed_components"] += 1
            continue

        try:
            with open(result_file, "r", encoding="utf-8") as f:
                result = json.load(f)
            
            # Extract metrics from per_case_results
            metrics_summary = {}
            latencies = []
            if "per_case_results" in result and result["per_case_results"]:
                # Calculate mean metrics across all cases
                all_metrics = {}
                for case in result["per_case_results"]:
                    for metric, value in case.get("metrics", {}).items():
                        if metric not in all_metrics:
                            all_metrics[metric] = []
                        all_metrics[metric].append(value)
                    
                    # Collect latencies
                    if "latency_seconds" in case:
                        latencies.append(case["latency_seconds"])
                
                for metric, values in all_metrics.items():
                    metrics_summary[metric] = sum(values) / len(values) if values else 0.0
            
            # Calculate P95 latency
            if latencies:
                latencies_sorted = sorted(latencies)
                p95_idx = int(len(latencies_sorted) * 0.95)
                p95_latency = latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)]
                mean_latency = sum(latencies) / len(latencies)
            else:
                p95_latency = result.get("p95_latency_seconds", 0)
                mean_latency = result.get("mean_latency_seconds", 0)
            
            aggregated["components"][component] = {
                "status": "success",
                "metrics": metrics_summary,
                "latency": {
                    "mean": mean_latency,
                    "p95": p95_latency,
                },
                "cases_run": result.get("cases_run", len(result.get("per_case_results", []))),
                "success_rate": result.get("success_rate", 1.0),
                "git_sha": result.get("git_sha"),
            }
            aggregated["summary"]["successful_components"] += 1
        except Exception as e:
            aggregated["components"][component] = {"status": "error", "error": str(e)}
            aggregated["summary"]["failed_components"] += 1

    return aggregated


def generate_markdown_report(aggregated: dict[str, Any], output_path: Path) -> None:
    """Generate markdown report from aggregated results."""
    lines = [
        "# Component Evaluation Unified Report",
        "",
        f"**Generated**: {aggregated['timestamp']}",
        "",
        "## Summary",
        "",
        f"- Total components: {aggregated['summary']['total_components']}",
        f"- Successful: {aggregated['summary']['successful_components']}",
        f"- Failed: {aggregated['summary']['failed_components']}",
        "",
        "## Component Results",
        "",
    ]

    for component, data in aggregated["components"].items():
        lines.append(f"### {component}")
        lines.append("")
        
        if data["status"] == "success":
            lines.append(f"- Status: ✅ Success")
            lines.append(f"- Cases run: {data['cases_run']}")
            lines.append(f"- Success rate: {data['success_rate']:.2%}")
            lines.append(f"- Mean latency: {data['latency']['mean']:.4f}s")
            lines.append(f"- P95 latency: {data['latency']['p95']:.4f}s")
            lines.append(f"- Git SHA: {data.get('git_sha', 'N/A')}")
            lines.append("")
            lines.append("**Metrics**:")
            for metric, value in data["metrics"].items():
                lines.append(f"- {metric}: {value:.4f}")
        else:
            lines.append(f"- Status: ❌ {data['status']}")
            lines.append(f"- Error: {data.get('error', 'Unknown')}")
        
        lines.append("")

    # Add weakest component analysis
    lines.append("## Weakest Component Analysis")
    lines.append("")
    lines.append("(Based on lowest mean key metric per component)")
    lines.append("")

    successful = {
        k: v for k, v in aggregated["components"].items() 
        if v["status"] == "success"
    }
    
    if successful:
        # Find component with lowest mean metric
        component_scores = {}
        for comp, data in successful.items():
            metrics = data.get("metrics", {})
            if metrics:
                mean_metric = sum(metrics.values()) / len(metrics)
                component_scores[comp] = mean_metric
        
        if component_scores:
            weakest = min(component_scores.items(), key=lambda x: x[1])
            lines.append(f"- **Weakest component**: {weakest[0]} (mean metric: {weakest[1]:.4f})")
        else:
            lines.append("- No metrics to analyze")
    else:
        lines.append("- No successful components to analyze")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run all component benchmarks and generate unified report")
    parser.add_argument("--runs", type=int, default=1, help="Number of runs per benchmark")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory (defaults to configured evaluation artifacts)")
    args = parser.parse_args()

    # Use the configured artifact root so relocation does not require code edits.
    if args.output_dir is None:
        output_dir = get_data_paths().experiments_dir / "agent_eval" / "component_benchmarks"
    else:
        output_dir = Path(args.output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Running all component benchmarks...")
    result_files = run_all_benchmarks(runs=args.runs, output_dir=output_dir)

    print("\nAggregating results...")
    aggregated = aggregate_results(result_files)

    # Save JSON
    json_path = output_dir / f"unified_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json_path.write_text(json.dumps(aggregated, indent=2), encoding="utf-8")
    print(f"JSON report saved to: {json_path}")

    # Save Markdown
    md_path = output_dir / f"unified_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    generate_markdown_report(aggregated, md_path)
    print(f"Markdown report saved to: {md_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
