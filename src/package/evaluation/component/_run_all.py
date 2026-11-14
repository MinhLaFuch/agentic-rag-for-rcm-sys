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
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Run all component benchmarks and collect results. runs đọc từ component_benchmarks.yaml trong từng CLI con."""
    if output_dir is None:
        output_dir = get_data_paths().output_dir("component_benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Component -> dataset map lives in configs/eval/component_benchmarks.yaml
    from package.config import load_config
    bench_cfg = load_config("eval/component_benchmarks")["component_benchmarks"]
    datasets = bench_cfg.get("datasets") or {}
    if not datasets:
        raise RuntimeError("component_benchmarks.yaml has no datasets map")
    components = list(datasets.items())

    results = {}

    for component, dataset in components:
        print(f"\n{'='*60}")
        print(f"Running {component} benchmark...")
        print(f"{'='*60}")

        info: dict[str, Any] = {"result_file": None, "error": None, "not_implemented": False}

        # Grounding cần Jev credential (judge.yaml api_key hoặc env fallback).
        # Thiếu credential -> skipped_no_credentials như multi_turn, thay vì
        # để mọi case fail do raise trong GroundingBenchmark.run_component.
        if component == "grounding" and not _jev_configured():
            info["status"] = "skipped_no_credentials"
            info["error"] = (
                "grounding needs a Jev credential: set JEV_API_KEY "
                "(configs/eval/judge.yaml) or TYPESAFE_API_KEY/OPENROUTER_API_KEY"
            )
            print("grounding: skipped — no Jev credentials configured")
            results[component] = info
            continue

        results[component] = _run_component_cli(component, dataset, info)

    # Backlog datasets (known unsupported features — expected failures, not
    # regressions). run_backlog=false -> status "skipped_backlog" trong report;
    # true -> chạy thật qua cùng component CLI.
    run_backlog = bool(bench_cfg.get("run_backlog", False))
    for label, spec in (bench_cfg.get("backlog_datasets") or {}).items():
        if isinstance(spec, str):
            spec = {"component": label, "dataset": spec}
        component = spec["component"]
        dataset = spec["dataset"]
        info = {"result_file": None, "error": None, "not_implemented": False,
                "backlog": True}
        if not run_backlog:
            info["status"] = "skipped_backlog"
            info["error"] = (
                "backlog dataset documents known unsupported features; "
                "set component_benchmarks.run_backlog: true to run, or invoke "
                f"--component {component} --dataset {dataset} directly"
            )
            print(f"{label}: skipped — backlog dataset (run_backlog=false)")
            results[label] = info
            continue
        results[label] = _run_component_cli(component, dataset, info)

    # Multi-turn conversation evaluation is not a component-benchmark case: it
    # needs a real LLM (PlanExecutor + Session over the fixture corpus). Run it
    # here so the unified report always shows an explicit status — a missing
    # provider must surface as "skipped_no_credentials", never silently absent.
    results["multi_turn"] = _run_multi_turn()

    return results


def _run_component_cli(component: str, dataset: str, info: dict[str, Any]) -> dict[str, Any]:
    """Chạy một component benchmark qua subprocess; điền info in-place."""
    try:
        cmd = [
            sys.executable, "-m", "package.evaluation.component.run",
            "--component", component,
            "--dataset", dataset,
        ]
        from package.config import get_data_paths
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=str(get_data_paths().src_root))
        print(result.stdout)

        if result.returncode != 0:
            print(f"Error running {component}: exit code {result.returncode}")
            print(f"stderr: {result.stderr}")
            info["error"] = (result.stderr or "").strip()[-500:] or f"exit code {result.returncode}"
            info["not_implemented"] = "not yet implemented" in (result.stderr or "").lower()
            return info

        for line in result.stdout.split('\n'):
            if "Results saved to:" in line:
                result_file = line.split("Results saved to:")[-1].strip()
                info["result_file"] = str(get_data_paths().src_root / result_file)
                break

        if info["result_file"] is None:
            print(f"Warning: {component} completed but no 'Results saved to:' line found in stdout")
            info["error"] = "completed but no 'Results saved to:' line in stdout"

    except Exception as e:
        print(f"Unexpected error running {component}: {e}")
        import traceback
        traceback.print_exc()
        info["error"] = str(e)

    return info


def _jev_configured() -> bool:
    """True khi Jev judge có credential: judge.yaml api_key hoặc env fallback
    (TYPESAFE_API_KEY / OPENROUTER_API_KEY — xem package/api/jev_provider.py)."""
    import os

    if os.environ.get("TYPESAFE_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
        return True
    try:
        from package.config import load_config

        return bool(load_config("eval/judge").get("api_key"))
    except Exception:
        return False


def _llm_configured() -> bool:
    """True when configs/agent/llm.yaml resolves a non-empty base_url."""
    from package.config import load_config
    try:
        return bool(load_config("agent/llm").get("base_url"))
    except Exception:
        return False


def _run_multi_turn() -> dict[str, Any]:
    """Run the multi-turn conversation evaluation as a report-visible step.

    Returns the same info shape as component runs plus ``status``:
    ``skipped_no_credentials`` when no LLM is configured, ``failed``/``success``
    is derived later from ``error``/``result_file`` like other components.
    """
    info: dict[str, Any] = {"result_file": None, "error": None, "not_implemented": False,
                            "status": "success"}
    if not _llm_configured():
        info["status"] = "skipped_no_credentials"
        info["error"] = ("multi-turn needs a real LLM: set LLM_BASE_URL/LLM_API_KEY "
                         "(configs/agent/llm.yaml) or pass config {'llm': {...}}")
        print("multi_turn: skipped — no LLM credentials configured")
        return info

    dataset = "package/evaluation/multi_turn/conversations.jsonl"
    cmd = [sys.executable, "-m", "package.evaluation.multi_turn._run",
           "--dataset", dataset]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False,
                                cwd=str(get_data_paths().src_root))
        print(result.stdout)
        if result.returncode != 0:
            info["status"] = "failed"
            info["error"] = (result.stderr or "").strip()[-500:] or f"exit code {result.returncode}"
            return info
        for line in result.stdout.split("\n"):
            if "Results saved to:" in line:
                info["result_file"] = str(get_data_paths().src_root / line.split("Results saved to:")[-1].strip())
                break
        if info["result_file"] is None:
            info["status"] = "failed"
            info["error"] = "completed but no 'Results saved to:' line in stdout"
    except Exception as e:
        info["status"] = "failed"
        info["error"] = str(e)
    return info


def _as_info(value: Any) -> dict[str, Any]:
    """Normalize a run_all_benchmarks entry to {result_file, error, not_implemented}."""
    if isinstance(value, dict):
        return {
            "result_file": value.get("result_file"),
            "error": value.get("error"),
            "not_implemented": bool(value.get("not_implemented")),
            "status": value.get("status"),
            "backlog": bool(value.get("backlog")),
        }
    # Legacy shape: plain path string or None
    return {"result_file": value, "error": None, "not_implemented": False}


def aggregate_results(result_files: dict[str, Any]) -> dict[str, Any]:
    """Aggregate all benchmark results into unified report."""
    aggregated = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {},
        "summary": {
            "total_components": len(result_files),
            "successful_components": 0,
            "failed_components": 0,
            "skipped_components": 0,
        },
    }

    for component, raw_info in result_files.items():
        info = _as_info(raw_info)
        result_file = info.get("result_file")

        if info.get("status") in ("skipped_no_credentials", "skipped_backlog"):
            aggregated["components"][component] = {
                "status": info["status"],
                "backlog": bool(info.get("backlog")),
                "quality_gate": "not_evaluated",
                "error": info.get("error") or "Skipped",
            }
            aggregated["summary"]["skipped_components"] += 1
            continue

        if info.get("not_implemented"):
            aggregated["components"][component] = {
                "status": "not_implemented",
                "quality_gate": "not_evaluated",
                "error": info.get("error") or "Evaluator not implemented",
            }
            aggregated["summary"]["failed_components"] += 1
            continue

        if result_file is None:
            aggregated["components"][component] = {
                "status": "failed",
                "quality_gate": "not_evaluated",
                "error": info.get("error") or "Benchmark did not run",
            }
            aggregated["summary"]["failed_components"] += 1
            continue

        try:
            with open(result_file, "r", encoding="utf-8") as f:
                result = json.load(f)

            # multi_turn writes a ConversationSummary, not a component-benchmark
            # result — map its fields instead of the per_case_results path.
            if component == "multi_turn":
                metrics_summary = dict(result.get("metrics") or {})
                metrics_summary["turn_success_rate"] = result.get("turn_success_rate")
                metrics_summary["conversation_success_rate"] = result.get("conversation_success_rate")
                # 11 conversations is too few for a meaningful p95 — report n/a,
                # never a fabricated 0.
                latency_p95 = (result.get("latency") or {}).get("p95")
                aggregated["components"][component] = {
                    "status": "success",
                    "quality_gate": "not_evaluated",
                    "thresholds_result": None,
                    "metrics": metrics_summary,
                    "latency": {
                        "mean": (result.get("latency") or {}).get("mean", 0) or 0,
                        "p95": latency_p95,
                    },
                    "cases_run": result.get("total_conversations", 0),
                    # failed_cases = failed CONVERSATIONS (not turns); older
                    # result files lack the field -> None, not a fake 0.
                    "failed_cases": result.get("failed_conversations"),
                    "failed_conversation_ids": result.get("failed_conversation_ids") or [],
                    "turn_completion_ratio": result.get("turn_completion_ratio"),
                    "failure_distribution": result.get("failure_distribution") or {},
                    "success_rate": None,
                    "git_sha": result.get("git_sha"),
                }
                aggregated["summary"]["successful_components"] += 1
                continue

            # Extract metrics from per_case_results.
            # NOTE: means are computed over cases that produced metrics (successful
            # runs only); failed_cases is reported separately so means are not misread.
            metrics_summary = {}
            latencies = []
            per_case = result.get("per_case_results", []) or []
            failed_cases = sum(1 for c in per_case if not c.get("success", True))
            if per_case:
                # Calculate mean metrics across all cases
                all_metrics = {}
                for case in per_case:
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

            # success_rate lives in result["metrics"] (written by ComponentEvaluator);
            # a missing key means unknown — report None, never default to a PASS.
            success_rate = result.get("metrics", {}).get("success_rate", result.get("success_rate"))

            # Quality gate: thresholds_result comes from the evaluator config
            # (configs/eval/component_benchmarks.yaml). None → not_evaluated.
            thresholds_result = result.get("thresholds_result")
            passed = thresholds_result.get("passed") if isinstance(thresholds_result, dict) else None
            if passed is True:
                quality_gate = "pass"
            elif passed is False:
                quality_gate = "fail"
            else:
                quality_gate = "not_evaluated"

            aggregated["components"][component] = {
                "status": "success",
                "backlog": bool(info.get("backlog")),
                "quality_gate": quality_gate,
                "thresholds_result": thresholds_result,
                "metrics": metrics_summary,
                "latency": {
                    "mean": mean_latency,
                    "p95": p95_latency,
                },
                "cases_run": result.get("cases_run", len(per_case)),
                "failed_cases": failed_cases,
                "success_rate": success_rate,
                "git_sha": result.get("git_sha"),
            }
            aggregated["summary"]["successful_components"] += 1
        except Exception as e:
            aggregated["components"][component] = {
                "status": "error",
                "quality_gate": "not_evaluated",
                "error": str(e),
            }
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
        f"- Skipped: {aggregated['summary'].get('skipped_components', 0)}",
        "",
        "## Component Results",
        "",
    ]

    for component, data in aggregated["components"].items():
        lines.append(f"### {component}")
        lines.append("")
        
        if data["status"] == "success":
            lines.append(f"- Status: ✅ Success")
            failed = data.get("failed_cases")
            cases_note = f" ({failed} failed)" if failed else ""
            lines.append(f"- Cases run: {data['cases_run']}{cases_note}")
            failed_ids = data.get("failed_conversation_ids") or []
            if failed_ids:
                lines.append(f"- Failed conversations: {', '.join(failed_ids)}")
            fd = data.get("failure_distribution") or {}
            if fd:
                lines.append(f"- Failure distribution: {fd}")
            tcr = data.get("turn_completion_ratio")
            if tcr is not None:
                lines.append(f"- Turn completion ratio (executed/scheduled): {tcr:.2%}")
                lines.append(
                    "- Note: measured on the synthetic fixture corpus, not real catalog data; "
                    "read turn_success_rate together with conversation_success_rate and "
                    "turn_completion_ratio (turns after a failure are not executed)."
                )
            gate = data.get("quality_gate", "not_evaluated")
            gate_icon = {"pass": "✅ PASS", "fail": "❌ FAIL", "not_evaluated": "⚪ NOT_EVALUATED"}[gate]
            lines.append(f"- Quality gate (thresholds): {gate_icon}")
            checks = (data.get("thresholds_result") or {}).get("checks") or {}
            for check, verdict in checks.items():
                lines.append(f"  - {check}: {verdict}")
            lines.append("")
            lines.append("**Execution Reliability**:")
            sr = data.get("success_rate")
            lines.append(f"- Success rate (ran without exception): {sr:.2%}" if sr is not None else "- Success rate (ran without exception): N/A")
            lines.append("")
            lines.append("**Performance**:")
            lines.append(f"- Mean latency: {data['latency']['mean']:.4f}s")
            p95 = data["latency"].get("p95")
            lines.append(f"- P95 latency: {p95:.4f}s" if p95 is not None else "- P95 latency: n/a")
            lines.append("")
            lines.append("**Functional Correctness Metrics**:")
            for metric, value in data["metrics"].items():
                lines.append(f"- {metric}: {value:.4f}")
            lines.append("")
            lines.append(f"- Git SHA: {data.get('git_sha', 'N/A')}")
        else:
            lines.append(f"- Status: ❌ {data['status']}")
            lines.append(f"- Error: {data.get('error', 'Unknown')}")

        lines.append("")

    # Add execution reliability analysis
    lines.append("## Execution Reliability Analysis")
    lines.append("")
    lines.append("Distinguishes component execution success from functional correctness.")
    lines.append("")

    successful = {
        k: v for k, v in aggregated["components"].items() 
        if v["status"] == "success"
    }
    
    if successful:
        lines.append("**Execution Success Rates**:")
        for comp, data in successful.items():
            success_rate = data.get('success_rate')
            if success_rate is None:
                lines.append(f"- {comp}: N/A (unknown)")
                continue
            status_icon = "✅" if success_rate >= 0.95 else "⚠️" if success_rate >= 0.8 else "❌"
            lines.append(f"- {comp}: {success_rate:.2%} {status_icon}")
        lines.append("")
    else:
        lines.append("- No successful components to analyze")
        lines.append("")

    # Add functional correctness analysis
    lines.append("## Functional Correctness Analysis")
    lines.append("")
    lines.append("Measures whether component behavior is correct when it executes successfully.")
    lines.append("")

    if successful:
        lines.append("**Correctness by Component**:")
        for comp, data in successful.items():
            metrics = data.get("metrics", {})
            if metrics:
                # Calculate mean correctness metric (excluding success_rate which is execution reliability)
                correctness_metrics = {k: v for k, v in metrics.items() if not k.endswith('_mean') or 'success' not in k}
                if correctness_metrics:
                    mean_correctness = sum(correctness_metrics.values()) / len(correctness_metrics)
                    status_icon = "✅" if mean_correctness >= 0.95 else "⚠️" if mean_correctness >= 0.8 else "❌"
                    lines.append(f"- {comp}: {mean_correctness:.2%} {status_icon}")
                else:
                    lines.append(f"- {comp}: No correctness metrics")
            else:
                lines.append(f"- {comp}: No metrics")
        lines.append("")

    # Add weakest component analysis
    lines.append("## Weakest Component Analysis")
    lines.append("")
    lines.append("(Based on lowest mean correctness metric per component)")
    lines.append("")

    if successful:
        # Find component with lowest mean correctness metric
        component_scores = {}
        for comp, data in successful.items():
            metrics = data.get("metrics", {})
            if metrics:
                correctness_metrics = {k: v for k, v in metrics.items() if not k.endswith('_mean') or 'success' not in k}
                if correctness_metrics:
                    mean_metric = sum(correctness_metrics.values()) / len(correctness_metrics)
                    component_scores[comp] = mean_metric
        
        if component_scores:
            weakest = min(component_scores.items(), key=lambda x: x[1])
            lines.append(f"- **Weakest component**: {weakest[0]} (mean correctness: {weakest[1]:.4f})")
        else:
            lines.append("- No correctness metrics to analyze")
    else:
        lines.append("- No successful components to analyze")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    """Main entry point. runs đọc từ configs/eval/component_benchmarks.yaml; output từ data_paths.outputs.component_benchmarks.

    Returns 0 only when every component produced a result; non-zero if any
    component failed, errored, or is not implemented.
    """
    output_dir = get_data_paths().output_dir("component_benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Running all component benchmarks...")
    result_files = run_all_benchmarks(output_dir=output_dir)

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

    failed = aggregated["summary"]["failed_components"]
    print(f"\nDone! failed_components={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
