"""Score one agent trajectory against its request. Failures count as zeros (an error is not a skipped sample)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from package.tools.corpus import ItemCorpus
from package.evaluation._schema import PLANNER_AGENTS
from package.evaluation.requests import AgentRequest
from package.evaluation.layer1_outcome import score_layer1_outcome
from package.evaluation.layer2_interaction import score_layer2_interaction
from package.evaluation.layer3_grounding import score_layer3_grounding
from package.evaluation.layer4_process import score_layer4_process
from package.evaluation.layer5_deployment import score_layer5_deployment


def score_trajectory(
    request: AgentRequest,
    trajectory: dict[str, Any],
    *,
    item2id: Mapping[str, int],
    corpus: ItemCorpus,
    k: int,
    seen_item_ids: set[int] | None = None,
) -> dict[str, Any]:
    """
    trajectory: {agent, plan, ask_user, steps[{tool, ok, invented_ids, latency_seconds, error_kind}], recommended[item_id],
                 usage{attempts, prompt_tokens, completion_tokens, latency_seconds}, error, truncated,
                 tools_available, wall_seconds, reflections, first_attempt_ok,
                 answer_status, answer_grounded, answer_fallback, inference_usage}   (the last four: Inference, see below)
    `steps` / `recommended` are the FINAL attempt (after plan-reflect), so task_success is "right after fixing";
    first_attempt_ok is "right without fixing". Trajectories written before plan-reflect: reflections=0, first_attempt_ok=None.
    Returns one flat row of numbers/bools/None (None = metric not defined for this agent/kind).

    Inference columns (None when the trajectory has no answer: baseline, or a trajectory written before Inference existed):
      answer_status_<status>     whether the answer had that status (their means are the share of each status)
      answer_grounded            the answer text passed the grounding checks      (only for status "ok", else None)
      answer_fallback            the LLM answer was replaced by the template      (only for status "ok", else None)
      inference_*                tokens / latency / attempts of Inference's own LLM calls, apart from the planner's `usage`
    None of them is read by task_success, the ranking metrics or any other column above.
    """
    agent = trajectory["agent"]
    is_planner = agent in PLANNER_AGENTS

    # Score each layer independently
    layer1 = score_layer1_outcome(request, trajectory, item2id=item2id, k=k, seen_item_ids=seen_item_ids)
    layer2 = score_layer2_interaction(request, trajectory, corpus=corpus)
    layer3 = score_layer3_grounding(trajectory)
    layer4 = score_layer4_process(request, trajectory)
    layer5 = score_layer5_deployment(trajectory)

    # Combine all layers into one row
    row: dict[str, Any] = {
        "request_id": request.request_id,
        "agent": agent,
        "kind": request.kind,
        "segment": request.segment,
    }
    row.update(layer1)
    row.update(layer2)
    row.update(layer3)
    row.update(layer4)
    row.update(layer5)

    # Special case: personalized planner without MemoryTool cannot honestly personalize
    # This override is applied in the combiner, not in individual layers
    if request.kind == "personalized" and is_planner and "MemoryTool" not in trajectory.get("tools_available", []):
        # a planner that cannot read the user's history has no honest way to personalize: not scored (asking back is fine)
        row["tool_selection_ok"] = row["task_success"] = None

    return row
