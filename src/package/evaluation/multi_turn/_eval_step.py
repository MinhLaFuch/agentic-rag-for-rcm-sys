"""Multi-turn evaluation step for run_agent_eval / campaign wiring.

Runs ``package.evaluation.multi_turn._run`` as a subprocess and records an
explicit status — never fake metrics. The output location is yaml-driven
(``agent_eval.multi_turn.output_dir``): ``None`` writes ``multi_turn.json``
into the experiment dir; a path redirects it — the campaign overlay points
it at ``campaigns/<id>/multi_turn/`` so the artifact lives in exactly one
place. Idempotent: an existing file with ``status: "success"`` is returned
as-is (resume), so campaign re-runs do not pay for the LLM calls again.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from package.config import get_data_paths, load_config

DEFAULT_DATASET = "package/evaluation/multi_turn/conversations.jsonl"
_MULTI_TURN_MODULE = "package.evaluation.multi_turn._run"
_SUCCESS_METRICS = (
    "turn_success_rate",
    "conversation_success_rate",
    "turn_completion_ratio",
    "total_turns_scheduled",
    "total_turns_executed",
    "failed_conversations",
)


def _llm_configured() -> bool:
    """True when configs/agent/llm.yaml resolves a non-empty base_url."""
    try:
        return bool(load_config("agent/llm").get("base_url"))
    except Exception:
        return False


def _write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_multi_turn_eval(
    *, dataset: str, output_path: str | Path, timeout_seconds: int = 1800,
    limits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the multi-turn evaluation once and return its status info.

    Returns ``{"status", "resumed", "output_path", "summary", "error"}`` where
    status is ``success`` | ``skipped_no_credentials`` | ``failed`` | ``error``.
    On success ``summary`` is the parsed ConversationSummary (+ "status").
    """
    out = Path(output_path)
    if not out.is_absolute():
        out = get_data_paths().experiments_dir / out
    out = out.resolve()

    # Resume: a previous success is final — the eval has no incremental state.
    if out.exists():
        try:
            prev = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            prev = None
        if isinstance(prev, dict) and prev.get("status") == "success":
            return {
                "status": "success",
                "resumed": True,
                "output_path": str(out),
                "summary": prev,
                "error": None,
            }

    if not _llm_configured():
        reason = (
            "multi-turn needs a real LLM: set LLM_BASE_URL/LLM_API_KEY "
            "(configs/agent/llm.yaml)"
        )
        _write_status(out, {"status": "skipped_no_credentials", "reason": reason,
                            "dataset": dataset})
        return {"status": "skipped_no_credentials", "resumed": False,
                "output_path": str(out), "summary": None, "error": reason}

    cmd = [
        sys.executable, "-m", _MULTI_TURN_MODULE,
        "--dataset", dataset,
        "--output", str(out),
    ]
    if limits:
        # agent_eval.multi_turn.limits -> runner; recorded in multi_turn.json,
        # enforcement is Phase-C (see RealAgentRunner.resolved_config).
        cmd += ["--limits-json", json.dumps(limits)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False,
            cwd=str(get_data_paths().src_root),
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        error = f"multi-turn eval timed out after {timeout_seconds}s"
        _write_status(out, {"status": "timeout", "error": error, "dataset": dataset})
        return {"status": "timeout", "resumed": False,
                "output_path": str(out), "summary": None, "error": error}
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        _write_status(out, {"status": "error", "error": error, "dataset": dataset})
        return {"status": "error", "resumed": False,
                "output_path": str(out), "summary": None, "error": error}

    if result.returncode == 0 and out.exists():
        try:
            summary = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            summary = None
        return {"status": "success", "resumed": False,
                "output_path": str(out), "summary": summary, "error": None}

    error = (result.stderr or result.stdout or "").strip()[-500:] or f"exit code {result.returncode}"
    _write_status(out, {"status": "failed", "error": error, "dataset": dataset})
    return {"status": "failed", "resumed": False,
            "output_path": str(out), "summary": None, "error": error}


def run_multi_turn_for_eval(cfg_block: dict[str, Any] | None, default_output_path: Path) -> dict[str, Any] | None:
    """Gate used by run_agent_eval: returns None when multi_turn is disabled.

    ``cfg_block`` is ``agent_eval.multi_turn`` from the merged config;
    ``default_output_path`` is ``<exp_dir>/multi_turn.json``.
    """
    block = cfg_block or {}
    if not block.get("enabled"):
        return None
    configured = block.get("output_dir")
    # output_dir is a directory; the artifact is always <dir>/multi_turn.json.
    # None -> caller's default (<exp_dir>/multi_turn.json).
    out = Path(configured) / "multi_turn.json" if configured else Path(default_output_path)
    return run_multi_turn_eval(
        dataset=str(block.get("dataset") or DEFAULT_DATASET),
        output_path=out,
        timeout_seconds=int(block.get("timeout_seconds") or 1800),
        limits=block.get("limits") or None,
    )


# Aggregated conversation metrics live under summary["metrics"] with a
# _mean/_std/_min/_max suffix (MultiTurnEvaluator._aggregate_metrics); the
# discriminating ones the campaign used to drop:
_NESTED_METRIC_KEYS = (
    "avg_item_match_rate_mean",
    "exclusion_compliance_mean",
    "clarification_compliance_mean",
    "no_result_compliance_mean",
    "reference_accuracy_mean",
    "tool_call_match_rate_mean",
)


def extract_multi_turn_metrics(summary: dict[str, Any] | None) -> dict[str, Any]:
    """Metrics worth reporting at campaign level (not used in comparisons)."""
    if not isinstance(summary, dict):
        return {}
    out = {k: summary.get(k) for k in _SUCCESS_METRICS if k in summary}
    nested = summary.get("metrics")
    if isinstance(nested, dict):
        out.update({k: nested[k] for k in _NESTED_METRIC_KEYS if k in nested})
    return out
