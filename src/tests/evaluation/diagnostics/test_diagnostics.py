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
    assert kd["step_errors"] == {"no_error": 1, "unknown_tool": 2, "tool_error": 1}
    assert kd["plan_errors"] == {"plan_invalid": 1, "provider_error": 1}


def test_error_taxonomy_groups_by_agent_and_kind_and_defaults_unknown():
    trajs = [
        _traj(agent="baseline", kind="cold_text", steps=[{"error_kind": None}]),
        {"agent": "planner", "steps": [{"error_kind": "exception"}]},  # no kind -> "unknown"
    ]
    out = error_taxonomy(trajs)
    assert out["baseline"]["cold_text"]["step_errors"] == {"no_error": 1}
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


def test_pool_stage_diagnostics_rates_distributions_and_rank():
    from package.evaluation.diagnostics import pool_stage_diagnostics

    rows = [
        {"agent": "type1", "kind": "similar",
         "target_in_any_path_pool": True, "target_in_pool_itemcf": True,
         "target_in_pool_sql": None, "target_reachable": True,
         "retrieved_by_itemcf": True, "retrieved_by_sql": None,
         "query_hit_any_title_token": False,
         "stage_lost": "filter", "rank_in_pool": 3},
        {"agent": "type1", "kind": "similar",
         "target_in_any_path_pool": False, "target_in_pool_itemcf": False,
         "target_in_pool_sql": None, "target_reachable": False,
         "retrieved_by_itemcf": False, "retrieved_by_sql": None,
         "query_hit_any_title_token": None,
         "stage_lost": "rank", "rank_in_pool": 7},
        {"agent": "baseline", "kind": "similar",
         "target_in_any_path_pool": None, "stage_lost": None, "rank_in_pool": None},
    ]
    out = pool_stage_diagnostics(rows)

    t1 = out["type1"]["similar"]
    assert t1["n_rows"] == 2
    # rate over measurable rows only: sql columns all-None -> absent, not 0
    assert "target_in_pool_sql" not in t1["rates"]
    assert t1["rates"]["target_in_any_path_pool"] == {"rate": 0.5, "n": 2}
    assert t1["rates"]["retrieved_by_itemcf"]["rate"] == 0.5
    # query_hit: one False, one None -> rate 0.0 over n=1
    assert t1["rates"]["query_hit_any_title_token"] == {"rate": 0.0, "n": 1}
    assert t1["stage_lost_counts"] == {"filter": 1, "rank": 1}
    assert t1["rank_in_pool"] == {"median": 5.0, "mean": 5.0, "n": 2}

    # all-None group still appears with n_rows but no rates/stage/rank blocks
    b = out["baseline"]["similar"]
    assert b["n_rows"] == 1
    assert "rates" not in b and "stage_lost_counts" not in b and "rank_in_pool" not in b


def test_pool_stage_diagnostics_empty_input():
    from package.evaluation.diagnostics import pool_stage_diagnostics
    assert pool_stage_diagnostics([]) == {}
