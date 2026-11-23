"""Aggregate retrieval pool/stage diagnostics from scored rows.

Pool verdicts and stage-loss fields live per-row in scored.jsonl; this module
rolls them up per (agent, kind) so diagnostics.json / metrics.json["diagnostics"]
carry citation-ready rates instead of requiring manual aggregation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np

# Boolean verdict columns aggregated as rates over rows where the value is
# measurable (non-None). Denominator = n, reported alongside each rate.
_RATE_COLUMNS = [
    "target_in_any_path_pool",
    "target_in_pool_sql",
    "target_in_pool_semantic",
    "target_in_pool_itemcf",
    "target_reachable",
    "retrieved_by_sql",
    "retrieved_by_semantic",
    "retrieved_by_itemcf",
    "query_hit_any_title_token",
]


def pool_stage_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate pool/stage diagnostic columns by agent and kind.

    Returns {agent: {kind: {...}}} where each kind entry contains:
      - n_rows: scored rows in the group
      - rates: {column: {"rate": mean over measurable rows, "n": measurable count}}
      - stage_lost_counts: distribution of stage_lost values ("mixed" included)
      - rank_in_pool: {"median", "mean", "n"} — lower rank is better
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row.get("agent", "unknown"), row.get("kind", "unknown"))].append(row)

    result: dict[str, Any] = {}
    for (agent, kind), group in sorted(groups.items()):
        entry: dict[str, Any] = {"n_rows": len(group)}

        rates: dict[str, Any] = {}
        for col in _RATE_COLUMNS:
            vals = [float(row[col]) for row in group if row.get(col) is not None]
            if vals:
                rates[col] = {"rate": float(np.mean(vals)), "n": len(vals)}
        if rates:
            entry["rates"] = rates

        lost = Counter(row["stage_lost"] for row in group if row.get("stage_lost") is not None)
        if lost:
            entry["stage_lost_counts"] = dict(sorted(lost.items()))

        ranks = [float(row["rank_in_pool"]) for row in group
                 if isinstance(row.get("rank_in_pool"), (int, float))]
        if ranks:
            entry["rank_in_pool"] = {
                "median": float(np.median(ranks)),
                "mean": float(np.mean(ranks)),
                "n": len(ranks),
            }

        result.setdefault(agent, {})[kind] = entry

    return result
