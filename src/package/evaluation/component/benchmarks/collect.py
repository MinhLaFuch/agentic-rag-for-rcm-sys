"""Collect per-request values from scored runs."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def collect(runs: list[list[dict[str, Any]]], agent: str, metric: str) -> tuple[dict[str, list[float]], dict[str, dict]]:
    """request_id -> list of per-run values (None values skipped); request_id -> {kind, segment}."""
    vals: dict[str, list[float]] = defaultdict(list)
    info: dict[str, dict] = {}
    seen: set[str] = set()
    for scored in runs:
        for r in scored:
            if r.get("agent") != agent:
                continue
            rid = r["request_id"]
            seen.add(rid)
            info[rid] = {"kind": r["kind"], "segment": r["segment"]}
            v = r.get(metric)
            if v is not None:
                vals[rid].append(float(v))
    for rid in seen:
        vals.setdefault(rid, [])
    return vals, info