"""Render memory utility analysis results as Markdown."""

from __future__ import annotations

from typing import Any


def render_markdown(result: dict[str, dict[str, Any]], meta: dict[str, Any]) -> str:
    L = [f"# Memory Utility: {meta['agent_a']} vs {meta['agent_b']}", ""]
    L.append(f"Runs: {meta['runs_a']} vs {meta['runs_b']} | resamples={meta.get('resamples')} | confidence={meta.get('confidence')} | min_n={meta.get('min_n')}")
    L.append(f"Dirs A: {', '.join(meta.get('dirs_a', []))}")
    L.append(f"Dirs B: {', '.join(meta.get('dirs_b', []))}")
    if meta.get("compat_warnings"):
        L.append("**Compatibility warnings:**")
        for w in meta["compat_warnings"]:
            L.append(f"- {w}")
    L.append("")

    for metric, groups in result.items():
        L.append(f"## {metric}")
        L.append("| group | n_paired | unscored (A/B) | mean_A | mean_B | diff | CI | run_std (A/B) | W/L/T | verdict |")
        L.append("|---|---:|---:|---:|---:|---:|---|---:|---:|---|")
        for label in sorted(groups.keys()):
            g = groups[label]
            if g["verdict"] in ("insufficient_n", "no_pairs", "inconclusive") and g["mean_baseline"] is None:
                L.append(f"| {label} | {g['n_paired']} | {g['n_unscored_baseline']}/{g['n_unscored_memory']} | - | - | - | - | - | {g['verdict']} |")
                continue
            f = lambda x: "n/a" if x is None else f"{x:.3f}"
            L.append(f"| {label} | {g['n_paired']} | {g['n_unscored_baseline']}/{g['n_unscored_memory']} | "
                     f"{f(g['mean_baseline'])} | {f(g['mean_memory'])} | {f(g['diff'])} "
                     f"[{f(g['ci_lower'])}, {f(g['ci_upper'])}] | {f(g['run_std_baseline'])}/{f(g['run_std_memory'])} | "
                     f"{g['wins']}/{g['losses']}/{g['ties']} | {g['verdict']} |")
        warns = sorted({w for g in groups.values() for w in g["warnings"]})
        if warns:
            L += [""] + [f"> {w}" for w in warns]
        L.append("")
    return "\n".join(L)