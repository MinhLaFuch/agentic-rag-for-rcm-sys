"""Aggregate scored rows: agent -> kind -> segment ("all" = every segment of that kind) -> mean of each metric."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

_ID_KEYS = {"request_id", "agent", "kind", "segment"}

# Columns for which we calculate percentiles (latency and token usage metrics)
_PERCENTILE_COLUMNS = {
    "wall_seconds",
    "llm_latency_seconds",
    "tool_latency_seconds",
    "prompt_tokens",
    "completion_tokens",
    "inference_latency_seconds",
    "inference_prompt_tokens",
    "inference_completion_tokens",
}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[(row["agent"], row["kind"], row["segment"])].append(row)
        buckets[(row["agent"], row["kind"], "all")].append(row)

    out: dict[str, Any] = {}
    for (agent, kind, segment), group in sorted(buckets.items()):
        entry: dict[str, Any] = {"n": len(group)}
        for key in sorted({key for row in group for key in row} - _ID_KEYS):
            values = [float(row[key]) for row in group if row.get(key) is not None]  # bool -> 0.0/1.0
            if values:
                entry[key] = float(np.mean(values))
                # Add percentiles for latency/token columns
                if key in _PERCENTILE_COLUMNS:
                    entry[f"{key}_p50"] = float(np.percentile(values, 50))
                    entry[f"{key}_p95"] = float(np.percentile(values, 95))
        out.setdefault(agent, {}).setdefault(kind, {})[segment] = entry
    return out
