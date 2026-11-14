"""Headless tests for the Gradio event handlers inside build_ui (run_demo.py).

Handlers are closures registered on the Blocks object; Gradio 6 exposes them via
``demo.fns`` (dict id -> BlockFunction). Each BlockFunction.fn takes plain Python
values (not components), so tests call it directly — no server, no LLM.

Covered wiring (scripts/demo/run_demo.py):
- on_clear_history issues a fresh session_key and empties turn history
- profile change / Clear history / New conversation all route to it
- on_submit forwards session_key only when Multi-turn is on
- status shows session_turns; turn history grows by one row
"""

from __future__ import annotations

import pytest

from package.demo import DemoResult
from scripts.demo.run_demo import build_ui
from tests.demo.fakes.offline_backend import OfflineDemoBackend


def _build():
    backend = OfflineDemoBackend()
    demo = build_ui(backend, profiles=backend.get_profiles(), default_inference_mode="template")
    return backend, demo


def _fns_named(demo, name: str) -> list:
    """All BlockFunctions registered under the same Python function name."""
    return [f.fn for f in demo.fns.values() if getattr(f.fn, "__name__", "") == name]


def _handler(demo, name: str):
    fns = _fns_named(demo, name)
    assert fns, f"no handler named {name!r} registered on the Blocks object"
    return fns[0]


def test_clear_history_issues_new_key_and_empties_history():
    _, demo = _build()
    fn = _handler(demo, "on_clear_history")

    history, key1 = fn()
    history2, key2 = fn()

    assert history == [] and history2 == []
    assert isinstance(key1, str) and isinstance(key2, str)
    assert key1 != key2  # mỗi lần clear = conversation mới


def test_profile_change_clear_and_new_conversation_all_issue_keys():
    """Ba trigger (profile change, Clear history, New conversation) đều gọi
    on_clear_history -> mỗi lần đều là key mới (run_demo.py:265-281)."""
    _, demo = _build()
    fns = _fns_named(demo, "on_clear_history")
    # profile_dropdown.change + clear_history_btn.click + new_conversation_btn.click
    assert len(fns) >= 3
    keys = {fn()[1] for fn in fns}
    assert len(keys) == len(fns)  # mỗi trigger trả key khác nhau


def _spy_backend(backend, result: DemoResult | None = None):
    """Wrap backend.respond to capture the DemoRequest it receives."""
    seen: list = []
    orig = backend.respond

    def spy(request):
        seen.append(request)
        return result if result is not None else orig(request)

    backend.respond = spy
    return seen


def test_multiturn_off_sends_none_session_key():
    backend, demo = _build()
    seen = _spy_backend(backend)
    submit = _handler(demo, "on_submit")

    submit("blank", "gợi ý game", False, False, 0, "planner", "template", [], "convkey1")

    assert seen[0].session_key is None  # multiturn=False -> single-turn


def test_multiturn_on_keeps_session_key():
    backend, demo = _build()
    seen = _spy_backend(backend)
    submit = _handler(demo, "on_submit")

    submit("blank", "gợi ý game", False, True, 0, "planner", "template", [], "convkey1")

    assert seen[0].session_key == "convkey1"


def test_submit_shows_session_turns_in_status():
    backend, demo = _build()
    _spy_backend(
        backend,
        DemoResult(status="ok", text="t", items=[], trace=None, usage={}, error=None, session_turns=2),
    )
    submit = _handler(demo, "on_submit")

    status_md = submit("blank", "hi", False, True, 0, "planner", "template", [], "k")[0]

    assert "**Conversation turn:** 2" in status_md


def test_submit_appends_turn_history_row():
    backend, demo = _build()
    _spy_backend(backend)
    submit = _handler(demo, "on_submit")

    out = submit("blank", "gợi ý game", False, False, 0, "planner", "template", [], "k")
    updated_history = out[-1]

    assert len(updated_history) == 1
    row = updated_history[0]
    assert row[0] == 1            # Turn number
    assert row[5] in {"ok", "ask_user", "no_result", "tool_error"}  # Status
    assert isinstance(row[6], int)  # #Items


def test_submit_empty_request_does_not_call_backend():
    backend, demo = _build()
    seen = _spy_backend(backend)
    submit = _handler(demo, "on_submit")

    status_md = submit("blank", "   ", False, False, 0, "planner", "template", [], "k")[0]

    assert "enter a request" in status_md.lower()
    assert seen == []
