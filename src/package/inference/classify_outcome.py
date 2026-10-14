from __future__ import annotations

from ._dataclass import AgentOutcome
from ._helper import cut

QUESTION_IGNORED = "question ignored: plan also had steps"


def classify_outcome(outcome: AgentOutcome) -> tuple[str, str | None]:
    """(status, reason) of an outcome. First matching rule wins; see docs/inference_contract.md section 5."""
    if outcome.question and outcome.n_steps == 0:
        return "ask_user", None
    notes = [QUESTION_IGNORED] if outcome.question else []  # the plan has steps, so it is judged by their result
    planner_errors = [e for e in outcome.errors if e.get("tool") == "planner"]
    if outcome.invented_ids:
        return "tool_error", cut(f"tool_error: invented ids {outcome.invented_ids}")
    if planner_errors:
        return "tool_error", cut(f"tool_error: planner: {planner_errors[0]['error']}")
    if outcome.items:
        failed = list(dict.fromkeys(e["tool"] for e in outcome.errors))
        if failed:
            notes.insert(0, f"partial: {', '.join(failed)} failed")
        return "ok", "; ".join(notes) or None
    if outcome.errors:
        first = outcome.errors[0]
        return "tool_error", cut(f"tool_error: {first['tool']}: {first['error']}")
    notes.insert(0, "no items returned" + (" (cold_start)" if outcome.cold_start else ""))
    return "no_result", "; ".join(notes)
