"""Visualization generation for evaluation results.

Charts are rendered as standalone SVG files (no plotting dependency).
Each generator reads the evaluation ``results`` dict and writes a real,
self-contained ``.svg`` that can be opened in any browser or embedded in
reports.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

_SVG_W = 720
_MARGIN = {"top": 40, "right": 20, "bottom": 60, "left": 70}


def _esc(text: Any) -> str:
    return html.escape(str(text))


def _svg_header(title: str, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SVG_W}" height="{height}" '
        f'font-family="sans-serif" font-size="12">\n'
        f'<rect width="100%" height="100%" fill="white"/>\n'
        f'<text x="{_SVG_W // 2}" y="24" text-anchor="middle" font-size="15" '
        f'font-weight="bold">{_esc(title)}</text>\n'
    )


def _scale(v: float, vmin: float, vmax: float, px_min: float, px_max: float) -> float:
    if vmax == vmin:
        return (px_min + px_max) / 2
    return px_min + (v - vmin) / (vmax - vmin) * (px_max - px_min)


def _axes(plot_x0: float, plot_y0: float, plot_x1: float, plot_y1: float,
          vmin: float, vmax: float, label: str = "") -> str:
    """Draw frame + 5 y ticks. y axis is inverted (value up)."""
    out = [
        f'<line x1="{plot_x0}" y1="{plot_y0}" x2="{plot_x0}" y2="{plot_y1}" stroke="#333"/>',
        f'<line x1="{plot_x0}" y1="{plot_y1}" x2="{plot_x1}" y2="{plot_y1}" stroke="#333"/>',
    ]
    for i in range(6):
        v = vmin + (vmax - vmin) * i / 5
        y = _scale(v, vmin, vmax, plot_y1, plot_y0)
        out.append(
            f'<line x1="{plot_x0 - 4}" y1="{y:.1f}" x2="{plot_x0}" y2="{y:.1f}" stroke="#333"/>'
        )
        out.append(
            f'<text x="{plot_x0 - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="10">'
            f'{v:.2f}</text>'
        )
    if label:
        out.append(
            f'<text x="16" y="{(plot_y0 + plot_y1) / 2:.0f}" text-anchor="middle" '
            f'transform="rotate(-90 16 {(plot_y0 + plot_y1) / 2:.0f})" font-size="11">'
            f'{_esc(label)}</text>'
        )
    return "\n".join(out)


def _bar_chart(
    title: str,
    categories: list[str],
    series: dict[str, list[float | None]],
    output_path: Path,
    y_label: str = "value",
    y_max: float | None = None,
) -> None:
    """Grouped vertical bar chart. series: name -> values aligned with categories."""
    n_cat = max(1, len(categories))
    names = list(series.keys())
    n_ser = max(1, len(names))
    plot_x0 = _MARGIN["left"]
    plot_x1 = _SVG_W - _MARGIN["right"]
    plot_y0 = _MARGIN["top"]
    plot_y1 = 400 - _MARGIN["bottom"]
    height = plot_y1 + _MARGIN["bottom"] + 30

    flat = [v for vals in series.values() for v in vals if v is not None]
    vmax = y_max if y_max is not None else (max(flat) * 1.15 if flat else 1.0)
    vmin = 0.0

    colors = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2"]
    parts = [_svg_header(title, height), _axes(plot_x0, plot_y0, plot_x1, plot_y1, vmin, vmax, y_label)]

    group_w = (plot_x1 - plot_x0) / n_cat
    bar_w = group_w / (n_ser * 1.4)
    for ci, cat in enumerate(categories):
        gx = plot_x0 + ci * group_w + group_w / 2
        for si, name in enumerate(names):
            vals = series[name]
            v = vals[ci] if ci < len(vals) and vals[ci] is not None else 0.0
            y_top = _scale(v, vmin, vmax, plot_y1, plot_y0)
            y_bot = _scale(0.0, vmin, vmax, plot_y1, plot_y0)
            x = gx - (n_ser * bar_w) / 2 + si * bar_w
            parts.append(
                f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w * 0.85:.1f}" '
                f'height="{max(0.0, y_bot - y_top):.1f}" fill="{colors[si % len(colors)]}">'
                f'<title>{_esc(cat)} / {_esc(name)}: {v:.3f}</title></rect>'
            )
        parts.append(
            f'<text x="{gx:.1f}" y="{plot_y1 + 16}" text-anchor="middle" '
            f'font-size="10" transform="rotate(-25 {gx:.1f} {plot_y1 + 16})">'
            f'{_esc(cat)}</text>'
        )

    # Legend
    lx = plot_x0
    for si, name in enumerate(names):
        parts.append(
            f'<rect x="{lx}" y="{height - 18}" width="10" height="10" fill="{colors[si % len(colors)]}"/>'
        )
        parts.append(f'<text x="{lx + 14}" y="{height - 9}" font-size="10">{_esc(name)}</text>')
        lx += 14 + 7 * len(str(name)) + 30

    parts.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")


def _heatmap(
    title: str,
    row_labels: list[str],
    col_labels: list[str],
    matrix: list[list[float]],
    output_path: Path,
) -> None:
    cell = 56
    left = 150
    top = 50
    width = left + len(col_labels) * cell + 30
    height = top + len(row_labels) * cell + 50
    flat = [v for row in matrix for v in row if v is not None]
    vmax = max(flat) if flat else 1.0
    vmin = min(flat) if flat else 0.0

    parts = [_svg_header(title, height)]
    for j, cl in enumerate(col_labels):
        parts.append(
            f'<text x="{left + j * cell + cell / 2:.0f}" y="{top - 8}" text-anchor="middle" '
            f'font-size="10" transform="rotate(-30 {left + j * cell + cell / 2:.0f} {top - 8})">'
            f'{_esc(cl)}</text>'
        )
    for i, rl in enumerate(row_labels):
        parts.append(
            f'<text x="{left - 8}" y="{top + i * cell + cell / 2 + 4:.0f}" text-anchor="end" '
            f'font-size="10">{_esc(rl)}</text>'
        )
        for j, cl in enumerate(col_labels):
            v = matrix[i][j] if i < len(matrix) and j < len(matrix[i]) else None
            if v is None:
                parts.append(
                    f'<rect x="{left + j * cell}" y="{top + i * cell}" width="{cell - 2}" '
                    f'height="{cell - 2}" fill="#eee"/>'
                )
                continue
            # blue intensity scale
            t = (v - vmin) / (vmax - vmin) if vmax != vmin else 0.5
            r = int(238 - t * 200)
            g = int(238 - t * 120)
            b = int(238 - t * 40)
            parts.append(
                f'<rect x="{left + j * cell}" y="{top + i * cell}" width="{cell - 2}" '
                f'height="{cell - 2}" fill="rgb({r},{g},{b})">'
                f'<title>{_esc(rl)} / {_esc(cl)}: {v:.3f}</title></rect>'
            )
            parts.append(
                f'<text x="{left + j * cell + cell / 2:.0f}" y="{top + i * cell + cell / 2 + 4:.0f}" '
                f'text-anchor="middle" font-size="10">{v:.2f}</text>'
            )
    parts.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")


def generate_layer_comparison_chart(
    results: dict[str, Any],
    output_path: Path,
) -> None:
    """Bar chart of mean metric values per evaluation layer (L1–L5)."""
    layers = results.get("layers") or []
    categories: list[str] = []
    series: dict[str, list[float]] = {}
    for layer in layers:
        name = layer.get("layer", f"L{len(categories) + 1}")
        categories.append(name)
        for metric, stat in (layer.get("metrics") or {}).items():
            mean = stat.get("mean") if isinstance(stat, dict) else stat
            if isinstance(mean, (int, float)):
                series.setdefault(metric, []).append(float(mean))
    # align series lengths to categories
    for name in series:
        vals = series[name]
        series[name] = vals + [None] * (len(categories) - len(vals))

    if not categories:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<!-- no layer data -->\n", encoding="utf-8")
        return
    _bar_chart(
        "Evaluation Layer Comparison",
        categories,
        series,
        output_path,
        y_label="metric mean",
        y_max=1.0,
    )


def generate_request_kind_heatmap(
    results: dict[str, Any],
    output_path: Path,
) -> None:
    """Heatmap of mean metrics per request kind."""
    kinds = results.get("request_kinds") or []
    row_labels = [k.get("kind", f"kind_{i}") for i, k in enumerate(kinds)]
    metric_names: list[str] = []
    for k in kinds:
        for m in (k.get("metrics") or {}):
            if m not in metric_names:
                metric_names.append(m)
    matrix: list[list[float | None]] = []
    for k in kinds:
        row: list[float | None] = []
        for m in metric_names:
            stat = (k.get("metrics") or {}).get(m)
            mean = stat.get("mean") if isinstance(stat, dict) else stat
            row.append(float(mean) if isinstance(mean, (int, float)) else None)
        matrix.append(row)

    if not row_labels or not metric_names:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<!-- no request-kind data -->\n", encoding="utf-8")
        return
    _heatmap(
        "Request Kind Performance",
        row_labels,
        metric_names,
        matrix,  # type: ignore[arg-type]
        output_path,
    )


def _funnel_stages(results: dict[str, Any]) -> list[tuple[str, float]]:
    funnel = results.get("retrieval_funnel")
    stages: list[tuple[str, float]] = []
    if isinstance(funnel, dict):
        for name, val in funnel.items():
            if isinstance(val, (int, float)):
                stages.append((str(name), float(val)))
            elif isinstance(val, dict):
                count = val.get("count", val.get("mean"))
                if isinstance(count, (int, float)):
                    stages.append((str(name), float(count)))
    elif isinstance(funnel, list):
        for item in funnel:
            if isinstance(item, dict):
                name = item.get("stage", item.get("name", "?"))
                count = item.get("count", item.get("value"))
                if isinstance(count, (int, float)):
                    stages.append((str(name), float(count)))
    return stages


def generate_retrieval_funnel_chart(
    results: dict[str, Any],
    output_path: Path,
) -> None:
    """Horizontal bar chart of candidate counts across retrieval stages."""
    stages = _funnel_stages(results)
    if not stages:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<!-- no retrieval funnel data -->\n", encoding="utf-8")
        return
    # reuse bar chart with single series, categories = stages
    _bar_chart(
        "Retrieval Funnel",
        [s[0] for s in stages],
        {"count": [s[1] for s in stages]},
        output_path,
        y_label="candidates",
    )


def generate_latency_distribution_chart(
    results: dict[str, Any],
    output_path: Path,
) -> None:
    """Histogram of latency values."""
    values = results.get("latency_values")
    if not isinstance(values, list) or not values:
        # fall back to per-metric value lists if present
        mv = results.get("metric_values") or {}
        values = mv.get("latency") or mv.get("wall_seconds")
    if not isinstance(values, list) or not values:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<!-- no latency data -->\n", encoding="utf-8")
        return

    nums = sorted(float(v) for v in values if isinstance(v, (int, float)))
    if not nums:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<!-- no numeric latency data -->\n", encoding="utf-8")
        return

    n_bins = min(20, max(5, int(len(nums) ** 0.5) + 1))
    lo, hi = nums[0], nums[-1]
    if hi == lo:
        hi = lo + 1e-6
    bins = [0] * n_bins
    for v in nums:
        idx = min(n_bins - 1, int((v - lo) / (hi - lo) * n_bins))
        bins[idx] += 1

    # percentiles for reference lines
    def pct(p: float) -> float:
        return nums[min(len(nums) - 1, int(p * (len(nums) - 1)))]

    p50, p95 = pct(0.5), pct(0.95)

    plot_x0 = _MARGIN["left"]
    plot_x1 = _SVG_W - _MARGIN["right"]
    plot_y0 = _MARGIN["top"]
    plot_y1 = 400 - _MARGIN["bottom"]
    height = plot_y1 + _MARGIN["bottom"] + 30
    vmax = max(bins) * 1.1 or 1.0

    parts = [_svg_header("Latency Distribution", height)]
    parts.append(_axes(plot_x0, plot_y0, plot_x1, plot_y1, 0, vmax, "count"))

    bin_w = (plot_x1 - plot_x0) / n_bins
    for i, c in enumerate(bins):
        x = plot_x0 + i * bin_w
        y_top = _scale(c, 0, vmax, plot_y1, plot_y0)
        y_bot = _scale(0, 0, vmax, plot_y1, plot_y0)
        parts.append(
            f'<rect x="{x + 1:.1f}" y="{y_top:.1f}" width="{bin_w - 2:.1f}" '
            f'height="{max(0.0, y_bot - y_top):.1f}" fill="#4C78A8"/>'
        )

    # x labels: bin edges in latency units
    for i in range(0, n_bins + 1, max(1, n_bins // 5)):
        v = lo + (hi - lo) * i / n_bins
        x = plot_x0 + i * bin_w
        parts.append(
            f'<text x="{x:.1f}" y="{plot_y1 + 16}" text-anchor="middle" font-size="10">'
            f'{v:.2f}s</text>'
        )

    # percentile markers
    for p, v, color in (("P50", p50, "#F58518"), ("P95", p95, "#E45756")):
        x = _scale(v, lo, hi, plot_x0, plot_x1)
        parts.append(
            f'<line x1="{x:.1f}" y1="{plot_y0}" x2="{x:.1f}" y2="{plot_y1}" '
            f'stroke="{color}" stroke-dasharray="4,3"/>'
        )
        parts.append(
            f'<text x="{x + 3:.1f}" y="{plot_y0 + 12}" font-size="10" fill="{color}">'
            f'{p}={v:.2f}s</text>'
        )

    parts.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")


def generate_multi_turn_performance_chart(
    results: dict[str, Any],
    output_path: Path,
) -> None:
    """Bar chart of multi-turn metrics (or per-turn success if turn data exists)."""
    mt = results.get("multi_turn") or {}
    if isinstance(mt, dict):
        # per-turn series if present
        turns = mt.get("by_turn") or mt.get("turns")
        if isinstance(turns, list) and turns:
            cats = [f"turn_{i + 1}" for i in range(len(turns))]
            vals = []
            for t in turns:
                if isinstance(t, dict):
                    v = t.get("success_rate", t.get("mean", t.get("value")))
                else:
                    v = t
                vals.append(float(v) if isinstance(v, (int, float)) else None)
            _bar_chart(
                "Multi-turn Performance by Turn",
                cats,
                {"metric": vals},
                output_path,
                y_label="success rate",
                y_max=1.0,
            )
            return
        # flat scalar metrics -> bar chart
        cats = list(mt.keys())
        vals = [float(v) for v in mt.values() if isinstance(v, (int, float))]
        cats = [c for c, v in zip(mt.keys(), mt.values()) if isinstance(v, (int, float))]
        if cats:
            _bar_chart(
                "Multi-turn Performance",
                cats,
                {"value": vals},
                output_path,
                y_label="metric",
            )
            return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("<!-- no multi-turn data -->\n", encoding="utf-8")


def generate_all_charts(
    results: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Generate all available charts for evaluation results.

    Args:
        results: Evaluation results
        output_dir: Directory to save charts

    Returns:
        Dict mapping chart names to file paths
    """
    charts: dict[str, Path] = {}

    if results.get("layers"):
        p = output_dir / "layer_comparison.svg"
        generate_layer_comparison_chart(results, p)
        charts["layer_comparison"] = p

    if results.get("request_kinds"):
        p = output_dir / "request_kind_heatmap.svg"
        generate_request_kind_heatmap(results, p)
        charts["request_kind_heatmap"] = p

    if results.get("retrieval_funnel"):
        p = output_dir / "retrieval_funnel.svg"
        generate_retrieval_funnel_chart(results, p)
        charts["retrieval_funnel"] = p

    latency = results.get("latency_values") or (
        (results.get("metric_values") or {}).get("latency")
    )
    if isinstance(latency, list) and latency:
        p = output_dir / "latency_distribution.svg"
        generate_latency_distribution_chart(results, p)
        charts["latency_distribution"] = p

    if results.get("multi_turn"):
        p = output_dir / "multi_turn_performance.svg"
        generate_multi_turn_performance_chart(results, p)
        charts["multi_turn_performance"] = p

    return charts
