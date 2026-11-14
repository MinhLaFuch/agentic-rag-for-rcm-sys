"""Read-only analysis of campaign_001 planner error trajectories (week47 investigation 2B).

Counts step-level errors in the campaign trajectory JSONL files and classifies
them into root-cause buckets. Also cross-checks task_success failures per
request kind from scored.jsonl. No LLM calls, no writes outside stdout.

Run from src/:
    PYTHONPATH=. python scripts/eda_diagnostic/analyze_campaign_001_planner_errors.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
LOGS = SRC / "experiments" / "logs" / "multi_domain"
CAMPAIGN = SRC / "experiments" / "agent_eval" / "campaigns" / "campaign_001"

EXPERIMENTS = {
    "exp_5": "planner/template/r0",
    "exp_6": "planner/template/r1",
    "exp_7": "planner/llm/r0 (partial)",
    "exp_8": "planner/llm/r1 (partial)",
    "exp_9": "planner_memory/template/r0",
    "exp_10": "planner_memory/template/r1",
    "exp_11": "planner_memory/llm/r0 (partial)",
    "exp_12": "planner_memory/llm/r1 (partial)",
}


def classify(error: str | None) -> str | None:
    """Root-cause bucket for a failed step's error text."""
    if not error:
        return None
    if "price_range.max" in error and "not found" in error:
        return "ref_null_price_range"
    if "NonExistentCategory" in error or "not found in the catalog" in error:
        return "category_not_in_catalog"
    if "time budget" in error or "SQLTimeOut" in error:
        return "search_time_budget"
    if "skipped, step" in error:
        return "cascade_skip"  # downstream of an earlier failed step
    if "candidates` is empty" in error or "candidates" in error and "empty" in error:
        return "empty_candidates"
    return "other"


def main() -> None:
    for exp, label in EXPERIMENTS.items():
        trajs = sorted(LOGS.glob(f"campaign_001_parameter_grid_{exp}_*_trajectories.jsonl"))
        if not trajs:
            print(f"{exp} ({label}): NO trajectory file")
            continue
        buckets: Counter[str] = Counter()
        traj_with_error: set[str] = set()
        root_causes: Counter[str] = Counter()
        n_records = 0
        provider_errors = 0
        for line in trajs[0].read_text(encoding="utf-8").splitlines():
            t = json.loads(line)
            n_records += 1
            provider_errors += int(bool(t.get("provider_error")))
            saw_root = False
            for step in t.get("steps", []):
                if step.get("ok", True) and not step.get("error"):
                    continue
                bucket = classify(step.get("error"))
                if bucket is None:
                    continue
                buckets[bucket] += 1
                traj_with_error.add(t["request_id"])
                if bucket != "cascade_skip":
                    root_causes[bucket] += 1
                    saw_root = True
        print(f"\n=== {exp} ({label}) — {n_records} records, provider_error={provider_errors}")
        print(f"    trajectories with >=1 failed step: {len(traj_with_error)}")
        for k, v in buckets.most_common():
            print(f"    step errors [{k}]: {v}")
        print(f"    root-cause trajectories (excl. cascade): {dict(root_causes)}")

    # task_success failures per kind from scored.jsonl (completed experiments only)
    print("\n=== task_success failures per kind (scored.jsonl) ===")
    for exp_dir in sorted(CAMPAIGN.glob("exp_*")):
        scored = exp_dir / "run_1" / "scored.jsonl"
        if not scored.exists():
            continue
        rows = [json.loads(l) for l in scored.read_text(encoding="utf-8").splitlines() if l.strip()]
        fails = Counter(r["kind"] for r in rows if not r.get("task_success"))
        total = len(rows)
        nfail = sum(fails.values())
        print(f"{exp_dir.name[:60]:<62} n={total:>3} task_fail={nfail:>3} {dict(fails)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
