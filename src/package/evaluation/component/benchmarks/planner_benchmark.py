"""Planner benchmark: isolated evaluation of plan-first planning.

Tests:
- Tool selection accuracy
- Argument correctness & completeness
- Plan/schema validity
- Reference resolution ($N.path)
- Constraint handling
- Clarification behavior (ask_user)
- Refusal-to-guess (must-not-guess cases)
- Stability across runs
- Latency and token/cost
"""

from __future__ import annotations

import re
import time
from typing import Any

from package.agents import PlanExecutor, build_tools
from package.api import build_llm_provider
from package.evaluation.component._evaluator import ComponentEvaluator
from package.evaluation.component._schema import BenchmarkCase, BenchmarkResult
from package.recommenders import ItemKNNRecommender
from package.tools import BaselineScorer

from .fixtures.create_test_corpus import create_test_corpus
from .fixtures.create_test_interactions import create_test_interactions
from .fixtures.create_test_mappings import create_test_mappings


class PlannerBenchmark(ComponentEvaluator):
    """Evaluator for Planner (PlanExecutor) component."""

    component_name = "planner"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        
        # Load LLM config from file or use provided config.
        # load_config resolves configs/ relative to the package root (not CWD)
        # and expands ${LLM_BASE_URL}/${LLM_API_KEY} env vars.
        from package.config import load_config

        llm_config = self.config.get("llm") or load_config("agent/llm")

        if not llm_config.get("base_url"):
            raise ValueError(
                "LLM base_url not configured. Set LLM_BASE_URL environment variable "
                "or provide llm.base_url in config (e.g., --config '{\"llm\": {\"base_url\": \"https://...\", \"model\": \"...\"}}')."
            )
        
        self.llm = build_llm_provider(llm_config)

        # Real tools over the synthetic fixture corpus (same fixtures the memory benchmark uses)
        interactions = create_test_interactions()
        user2id, item2id, _ = create_test_mappings(interactions)
        corpus = create_test_corpus()
        knn = ItemKNNRecommender(10).fit(interactions[["user_idx", "item_idx"]])
        agent_tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus)
        # for_planner_memory: the planner SYSTEM_PROMPT advertises MemoryTool and
        # the multi-turn runner / smoke script / live memory executor all use it.
        self.tools = agent_tools.for_planner_memory()
        self._tools_by_name = {t.name: t for t in self.tools}
        self.executor = PlanExecutor(llm=self.llm, tools=self.tools, reflect_rounds=0)

    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Run Planner with real tools."""
        user_request = case_input.get("user_request", "")
        started = time.perf_counter()

        steps = self.executor.plan(user_request)
        question = self.executor.last_question
        latency = time.perf_counter() - started

        return {
            "steps": steps,
            "question": question,
            "latency_seconds": latency,
            "usage": self.executor.last_usage,
        }

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score planner output against expected."""
        actual_steps = actual_output.get("steps", [])
        actual_question = actual_output.get("question")
        expected_steps = expected.get("steps", [])
        expected_question = expected.get("question")

        metrics = {
            "tool_selection_accuracy": 0.0,
            "argument_correctness": 0.0,
            "plan_validity": 0.0,
            "step_validity_rate": 0.0,
            "reference_correctness": 0.0,
            "constraint_handling": 0.0,
            "clarification_precision": 0.0,
            "clarification_recall": 0.0,
        }

        # Check if expected question matches (for ambiguous cases).
        # precision is token-F1, not exact match: two differently-worded but
        # equivalent questions should not score 0.
        expected_question = expected.get("question")
        requires_clarification = bool(expected.get("requires_clarification"))
        if expected_question is not None:
            metrics["clarification_precision"] = _token_f1(actual_question, expected_question)
            metrics["clarification_recall"] = 1.0 if actual_question is not None else 0.0
        else:
            # Should not ask question
            metrics["clarification_precision"] = 1.0 if actual_question is None else 0.0
            metrics["clarification_recall"] = 1.0

        # Plan validity, checked against the REAL tool schemas (not the dataset):
        # every step must name a real tool, use only declared args, provide all
        # required args, and only reference earlier steps with valid $N.path refs.
        validity = [_step_error(s, i, self._tools_by_name) for i, s in enumerate(actual_steps, 1)]
        bad = [e for e in validity if e]
        metrics["step_validity_rate"] = (len(validity) - len(bad)) / len(validity) if validity else 1.0
        metrics["plan_validity"] = 0.0 if bad else 1.0

        # Tool selection accuracy
        if len(actual_steps) == len(expected_steps):
            correct_tools = sum(
                1 for a, e in zip(actual_steps, expected_steps) if a.get("tool") == e.get("tool")
            )
            metrics["tool_selection_accuracy"] = correct_tools / len(expected_steps) if expected_steps else 1.0

        # Argument correctness (simple field match)
        if len(actual_steps) == len(expected_steps):
            correct_args = 0
            total_args = 0
            for a, e in zip(actual_steps, expected_steps):
                a_args = a.get("args", {})
                e_args = e.get("args", {})
                for key in e_args:
                    total_args += 1
                    if a_args.get(key) == e_args.get(key):
                        correct_args += 1
            metrics["argument_correctness"] = correct_args / total_args if total_args > 0 else 1.0

        # Refusal to guess: only defined on cases flagged requires_clarification.
        # Distinct from clarification_recall ("did it ask at all"): this penalizes
        # GUESSING — producing steps, or asking AND stepping, when required
        # information is missing. Emitted only where the flag exists so the
        # aggregate never averages over cases where the concept does not apply.
        if requires_clarification:
            metrics["refusal_to_guess"] = (
                1.0 if actual_question is not None and not actual_steps else 0.0
            )
        # Mirror metric on the other side: on cases that do NOT require
        # clarification, asking anyway is an unnecessary clarification.
        else:
            metrics["unnecessary_clarification_rate"] = (
                1.0 if actual_question is None else 0.0
            )

        # Reference correctness (check if $N.path format is used correctly)
        # Simplified: just check if references are present when expected
        has_references = any("$" in str(a.get("args", {})) for a in actual_steps)
        expected_references = any("$" in str(e.get("args", {})) for e in expected_steps)
        metrics["reference_correctness"] = 1.0 if has_references == expected_references else 0.0

        # Constraint handling (check if filters match expected)
        if len(actual_steps) == len(expected_steps):
            correct_filters = 0
            total_filters = 0
            for a, e in zip(actual_steps, expected_steps):
                a_filters = a.get("args", {}).get("filters", {})
                e_filters = e.get("args", {}).get("filters", {})
                for key in e_filters:
                    total_filters += 1
                    if a_filters.get(key) == e_filters.get(key):
                        correct_filters += 1
            metrics["constraint_handling"] = correct_filters / total_filters if total_filters > 0 else 1.0

        return metrics


_REF_RE = re.compile(r"^\$(\d+)((?:\.[\w*]+)*)$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _token_f1(actual: str | None, expected: str) -> float:
    """Token-level F1 between an actual question and the expected one."""
    if not actual:
        return 0.0
    a, b = set(_TOKEN_RE.findall(actual.lower())), set(_TOKEN_RE.findall(expected.lower()))
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    if not overlap:
        return 0.0
    precision, recall = overlap / len(a), overlap / len(b)
    return 2 * precision * recall / (precision + recall)


def _iter_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_strings(v)


def _step_error(step: Any, position: int, tools_by_name: dict[str, Any]) -> str | None:
    """First schema violation in a planned step, validated against the REAL tool
    input_schema — never against dataset expectations. `position` is 1-based;
    a $N.path ref may only point at steps 1..position-1."""
    if not isinstance(step, dict):
        return "step is not an object"
    name = step.get("tool")
    tool = tools_by_name.get(name)
    if tool is None:
        return f"unknown tool {name!r}"
    schema = tool.input_schema or {}
    args = step.get("args") or {}
    if not isinstance(args, dict):
        return "args is not an object"
    unknown = sorted(set(args) - set(schema))
    if unknown:
        return f"unknown args {unknown} for {name}"
    for key, spec in schema.items():
        # Required = spec string has no 'default' and no 'None' (same rule the
        # planner prompt states). Nested dict specs (e.g. FilterTool.filters)
        # are treated as optional groups — but their keys ARE validated below.
        required = isinstance(spec, str) and "default" not in spec and "None" not in spec
        if required and key not in args:
            return f"missing required arg {key!r} for {name}"
        if isinstance(spec, dict) and isinstance(args.get(key), dict):
            # spec keys may combine alternatives ("price_min / price_max")
            allowed = {part.strip() for k in spec for part in k.split("/")}
            bad_nested = sorted(set(args[key]) - allowed)
            if bad_nested:
                return f"unknown {key} keys {bad_nested} for {name}"
    for s in _iter_strings(args):
        if s.startswith("$S."):
            return f"session ref {s!r} but benchmark runs without session"
        m = _REF_RE.match(s)
        if m:
            n = int(m.group(1))
            if not 1 <= n < position:
                return f"ref {s!r} points at step {n}, only steps 1..{position - 1} have run"
        elif s.startswith("$"):
            return f"malformed ref {s!r}"
    return None
