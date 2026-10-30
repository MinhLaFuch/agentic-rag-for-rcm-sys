from __future__ import annotations

import json
import time
from typing import Any

from ...api import LLMMessage, LLMProvider
from ...api import LLMProviderError
from ...tools.base import Tool
from ._helper import _blocks_reflect, _compute_execution_quality, _extract_plan, _invented_ids, _is_quality_improvement, _reflect_problem, _resolve_refs, _resolve_session_refs_only, _simplify_args_for_log, _step_report, _summarize_output, _unknown_args
from .._limits import get_agent_limits, get_memory_limits
from ._prompt import SYSTEM_PROMPT
from ..toolkit import build_tool_prompt
from ..session import Session

RETRY_NOTICE = (
    "Your previous reply was rejected: {error}\n"
    "Reply again with ONLY the JSON object described in the system message."
)

REFLECT_NOTICE = (
    "Your plan was executed, but {problem}\n"
    "Steps that ran (a failed step also skips every step that references it):\n{report}\n"
    "Reply again with the COMPLETE corrected plan as ONLY the JSON object described in the system message. "
    "Change only what is wrong and keep every rule: never invent ids, and references may only use fields listed under `returns`."
)


class PlanExecutor:
    """
    Plan-first executor: one LLM call writes the whole JSON plan, then the steps run in order.
    Limits (max_steps, plan_retries, reflect_rounds, max_tokens, temperature) default to configs/agent/agent.yaml.

    plan-reflect: when a plan ran but a step failed, or it produced no item (and is not an ask_user), run() sends the
    LLM the step report (REFLECT_NOTICE) and runs the corrected plan, up to `reflect_rounds` times (0 = off).
    It never reflects when a step used an invented id, or hit the SQL time budget (a new plan would not help).
    A reflect reply that is not a usable plan (or a provider error during reflect) is dropped and the previous result is kept.

    After plan()/run() the `last_*` attributes describe the latest request:
      last_plan / last_question  the parsed plan and the clarifying question (ask_user)
      last_response              LLMResponse of the final LLM call (a reflect reply too, even an unusable one)
      last_usage                 tokens / latency / attempts summed over all LLM calls, reflect included
      last_truncated             True if the final plan was cut to max_steps
      last_reflections           reflect rounds used (an unusable reply counts)
      last_first_attempt_ok      True if the first run had no failed step and returned items (or asked the user)
      last_attempt_plans         the plan of each attempt, first to last (last_plan / run() results = the last one)
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: list[Tool],
        max_tokens: int | None = None,
        temperature: float | None = None,
        max_steps: int | None = None,
        plan_retries: int | None = None,
        reflect_rounds: int | None = None,
        session: Session | None = None,
    ) -> None:
        limits = get_agent_limits()
        memory_limits = get_memory_limits()
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.max_tokens = limits.max_tokens if max_tokens is None else max_tokens
        self.temperature = limits.temperature if temperature is None else temperature
        self.max_steps = limits.max_steps if max_steps is None else max_steps
        self.plan_retries = limits.plan_retries if plan_retries is None else plan_retries
        self.reflect_rounds = limits.reflect_rounds if reflect_rounds is None else reflect_rounds
        if self.reflect_rounds < 0:
            raise ValueError("reflect_rounds must be >= 0")
        self.session = session or Session(
            max_turns=10,
            max_shown_items=50,
            max_candidates=100,
            max_turn_chars=500,
        )
        self.last_response = None
        self.last_reflections = 0
        self.last_first_attempt_ok = True
        self.last_attempt_plans: list[list[dict[str, Any]]] = []
        self.last_plan: list[dict[str, Any]] = []
        self.last_question: str | None = None
        self.last_truncated = False
        self.last_usage: dict[str, Any] = {}
        self._messages: list[LLMMessage] = []

    def _complete(self, messages: list[LLMMessage]):
        resp = self.llm.complete(
            messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format_json=True,
        )
        self.last_response = resp
        self.last_usage["attempts"] += 1
        self.last_usage["prompt_tokens"] += resp.prompt_tokens or 0
        self.last_usage["completion_tokens"] += resp.completion_tokens or 0
        self.last_usage["latency_seconds"] += resp.latency_seconds or 0.0
        return resp

    def plan(self, user_request: str) -> list[dict[str, Any]]:
        # Inject session state into the system prompt
        session_state = json.dumps(self.session.to_dict(), ensure_ascii=False)
        system = SYSTEM_PROMPT.format(
            tools=build_tool_prompt(list(self.tools.values())),
            session_state=session_state
        )
        messages = [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user_request)]
        self.last_plan, self.last_question, self.last_truncated = [], None, False
        self.last_reflections, self.last_first_attempt_ok, self.last_attempt_plans = 0, True, []
        self.last_usage = {"attempts": 0, "prompt_tokens": 0, "completion_tokens": 0, "latency_seconds": 0.0}

        steps: list[dict[str, Any]] = []
        question: str | None = None
        for attempt in range(self.plan_retries + 1):
            resp = self._complete(messages)
            try:
                steps, question = _extract_plan(resp.text)
                break
            except ValueError as exc:
                if attempt == self.plan_retries:
                    raise
                messages = [
                    *messages,
                    LLMMessage(role="assistant", content=resp.text),
                    LLMMessage(role="user", content=RETRY_NOTICE.format(error=exc)),
                ]

        if len(steps) > self.max_steps:
            steps, self.last_truncated = steps[: self.max_steps], True
        self.last_plan, self.last_question = steps, question
        self.last_attempt_plans = [steps]
        self._messages = messages  # system + request (+ any JSON-retry exchange); reflect rebuilds from the first two
        return steps

    def run(self, user_request: str) -> list[dict[str, Any]]:
        results = self._execute(self.plan(user_request), user_request)
        problem = _reflect_problem(results, self.last_question)
        self.last_first_attempt_ok = problem is None
        messages = [*self._messages[:2], LLMMessage(role="assistant", content=self.last_response.text)]

        # Track quality for reflection quality gate
        previous_quality = _compute_execution_quality(results)
        best_results = results
        best_quality = previous_quality

        while problem and not _blocks_reflect(results) and self.last_reflections < self.reflect_rounds:
            self.last_reflections += 1
            notice = REFLECT_NOTICE.format(problem=problem, report=_step_report(results))
            messages = [*messages, LLMMessage(role="user", content=notice)]
            try:
                resp = self._complete(messages)
                steps, question = _extract_plan(resp.text)
            except (ValueError, LLMProviderError):
                break  # an unusable reply must not cost the result we already have
            if not steps and not question:
                break
            self.last_truncated = len(steps) > self.max_steps
            steps = steps[: self.max_steps]
            self.last_plan, self.last_question = steps, question
            self.last_attempt_plans.append(steps)
            new_results = self._execute(steps, user_request)
            new_quality = _compute_execution_quality(new_results)

            # Quality gate: only accept reflected plan if it improves
            if _is_quality_improvement(best_quality, new_quality):
                best_results = new_results
                best_quality = new_quality
                results = new_results
            else:
                # Keep the previous best result
                results = best_results

            problem = _reflect_problem(results, question)
            messages = [*messages, LLMMessage(role="assistant", content=resp.text)]

        # Update session state after successful execution
        self._update_session(user_request, results)

        return results

    def _update_session(self, user_request: str, results: list[dict[str, Any]]) -> None:
        """Update session state after each turn based on execution results."""
        # Add the turn
        plan_text = json.dumps(self.last_plan, ensure_ascii=False)
        answer = self.last_response.text if self.last_response else ""
        self.session.add_turn(user_request, plan_text, answer)

        # Extract shown items and candidates from results
        shown_items = []
        candidates = []
        ranked = []

        for step in results:
            if not step["ok"]:
                continue
            data = step.get("data", {})
            tool_name = step.get("tool", "")

            # QueryTool shows items
            if tool_name == "QueryTool":
                items = data.get("items", [])
                shown_items.extend([i.get("item_id") for i in items if isinstance(i, dict) and "item_id" in i])

            # SQLTool/SemanticSearchTool provide candidates
            if tool_name in ("SQLTool", "SemanticSearchTool"):
                step_candidates = data.get("candidates", [])
                candidates.extend(step_candidates)

            # RecoModelTool provides ranked items
            if tool_name == "RecoModelTool":
                step_ranked = data.get("ranked", [])
                ranked.extend([r.get("item_id") for r in step_ranked if isinstance(r, dict) and "item_id" in r])

        self.session.add_shown_items(shown_items)
        self.session.set_candidates(candidates, ranked)

    def _execute(self, steps: list[dict[str, Any]], user_request: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for step in steps:
            started = time.perf_counter()
            name = step.get("tool")
            tool = self.tools.get(name) if name else None
            raw_args = step.get("args") or {}
            entry: dict[str, Any] = {"tool": name, "ok": False, "data": {}, "error": None, "invented_ids": [], "error_kind": None}
            # Log args before validation (for debugging failed steps)
            entry["args"] = _simplify_args_for_log(raw_args)
            if tool is None:
                entry["error"] = "unknown tool"
                entry["error_kind"] = "unknown_tool"
            elif unknown := _unknown_args(tool, raw_args):
                entry["error"] = unknown  # actionable, and the tool is not called with args it does not declare
                entry["error_kind"] = "unknown_args"
            else:
                # Resolve session references first (for invented ID check)
                args_for_check = _resolve_session_refs_only(raw_args, self.session)
                if invented := _invented_ids(args_for_check, user_request, self.session.get_valid_ids()):
                    entry["error"] = f"id(s) not found in the request or session (invented?): {invented}"
                    entry["invented_ids"] = invented  # the tool is NOT executed with an id the user never gave
                    entry["error_kind"] = "invented_id"
                else:
                    try:
                        # Resolve step references for actual execution
                        resolved_args = _resolve_refs(raw_args, results, self.session)
                        res = tool(agent="planner", **resolved_args)
                        entry.update(ok=res.ok, data=res.data, error=res.error)
                        # Update args with resolved values
                        entry["args"] = _simplify_args_for_log(resolved_args)
                        entry["output_summary"] = _summarize_output(res.data, name)
                        if "note" in res.data:
                            entry["note"] = res.data["note"]
                        # Tool error (ok=False) but no exception
                        if not res.ok:
                            entry["error_kind"] = "tool_error"
                    except ValueError as exc:
                        # Distinguish reference errors from other ValueErrors
                        error_msg = str(exc)
                        if "step" in error_msg and ("has not run yet" in error_msg or "failed" in error_msg or "not found" in error_msg):
                            entry["error"] = error_msg
                            entry["error_kind"] = "bad_reference"
                        else:
                            entry["error"] = f"{type(exc).__name__}: {exc}"
                            entry["error_kind"] = "exception"
                    except Exception as exc:  # args sai tên/kiểu (TypeError...) không được làm hỏng các step còn lại
                        entry["error"] = f"{type(exc).__name__}: {exc}"
                        entry["error_kind"] = "exception"
            entry["latency_seconds"] = round(time.perf_counter() - started, 6)
            results.append(entry)
        return results
