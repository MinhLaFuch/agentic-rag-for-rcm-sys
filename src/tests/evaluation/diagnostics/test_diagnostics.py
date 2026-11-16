"""Unit tests for package.evaluation.diagnostics aggregations."""

from package.evaluation.diagnostics import error_taxonomy, reflection_diagnostics


def _traj(agent="planner", kind="constrained", steps=None, error=None, provider_error=False):
    return {
        "agent": agent,
        "kind": kind,
        "request_id": "r1",
        "steps": steps or [],
        "error": error,
        "provider_error": provider_error,
    }


def _row(agent="planner", kind="constrained", **kw):
    base = {
        "agent": agent,
        "kind": kind,
        "first_attempt_ok": True,
        "task_success": 1.0,
        "reflections": 0,
        "constraint_satisfaction": 1.0,
        "n_recommended": 5,
    }
    base.update(kw)
    return base


def test_error_taxonomy_counts_step_and_plan_errors():
    trajs = [
        _traj(steps=[
            {"error_kind": None},
            {"error_kind": "unknown_tool"},
            {"error_kind": "tool_error"},
        ]),
        _traj(
            steps=[{"error_kind": "unknown_tool"}],
            error="ValueError: bad plan",
            provider_error=True,
        ),
    ]
    out = error_taxonomy(trajs)
    kd = out["planner"]["constrained"]
    assert kd["step_errors"] == {"None": 1, "unknown_tool": 2, "tool_error": 1}
    assert kd["plan_errors"] == {"plan_invalid": 1, "provider_error": 1}


def test_error_taxonomy_groups_by_agent_and_kind_and_defaults_unknown():
    trajs = [
        _traj(agent="baseline", kind="cold_text", steps=[{"error_kind": None}]),
        {"agent": "planner", "steps": [{"error_kind": "exception"}]},  # no kind -> "unknown"
    ]
    out = error_taxonomy(trajs)
    assert out["baseline"]["cold_text"]["step_errors"] == {"None": 1}
    assert out["planner"]["unknown"]["step_errors"] == {"exception": 1}
    # plan_errors always present even with no plan-level errors
    assert out["planner"]["unknown"]["plan_errors"] == {"plan_invalid": 0, "provider_error": 0}


def test_reflection_diagnostics_rescue_rate_and_reflections():
    rows = [
        _row(first_attempt_ok=False, task_success=1.0, reflections=1),
        _row(first_attempt_ok=False, task_success=0.0, reflections=2),
        _row(first_attempt_ok=True, task_success=1.0, reflections=0),
    ]
    kd = reflection_diagnostics(rows)["planner"]["constrained"]
    assert kd["n_first_failed"] == 2
    assert kd["rescue_rate"] == 0.5
    assert kd["mean_reflections"] == 1.0


def test_reflection_diagnostics_rescue_rate_none_without_first_failures():
    kd = reflection_diagnostics([_row()])["planner"]["constrained"]
    assert kd["n_first_failed"] == 0
    assert kd["rescue_rate"] is None


def test_reflection_diagnostics_rescue_rate_skips_missing_task_success():
    rows = [
        _row(first_attempt_ok=False, task_success=None, reflections=1),
        _row(first_attempt_ok=False, task_success=1.0, reflections=1),
    ]
    kd = reflection_diagnostics(rows)["planner"]["constrained"]
    assert kd["rescue_rate"] == 1.0


def test_reflection_diagnostics_constraint_blind_spot_rate():
    rows = [
        # blind spot: constraint violated, no reflection
        _row(constraint_satisfaction=0.5, reflections=0),
        # reflected failure is NOT a blind spot
        _row(constraint_satisfaction=0.5, reflections=1),
        # satisfied constraint is not a blind spot
        _row(constraint_satisfaction=1.0, reflections=0),
        # no recommendations -> excluded from denominator
        _row(constraint_satisfaction=0.0, reflections=0, n_recommended=0),
    ]
    kd = reflection_diagnostics(rows)["planner"]["constrained"]
    assert kd["constraint_blind_spot_rate"] == 1 / 3


def test_reflection_diagnostics_blind_spot_none_for_unmeasurable_kinds():
    # personalized has no constraint_satisfaction -> None, not 0.0
    kd = reflection_diagnostics([_row(kind="personalized", constraint_satisfaction=None)])["planner"]["personalized"]
    assert kd["constraint_blind_spot_rate"] is None
    # exclusion is oracle but scores exclusion_compliance -> stays None too
    kd = reflection_diagnostics([_row(kind="exclusion", constraint_satisfaction=None)])["planner"]["exclusion"]
    assert kd["constraint_blind_spot_rate"] is None
