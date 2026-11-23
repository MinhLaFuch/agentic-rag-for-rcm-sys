"""Headless multi-turn session tests for LiveBackend (test doubles only, no LLM).

Covers session_key -> Session bookkeeping: turn counting, isolation between
keys, and single-turn behavior when no key is sent.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from package.demo import DemoRequest, DemoResult, LiveBackend
from package.demo.backend import live_backend as module


def _request(text: str, session_key: str | None = None) -> DemoRequest:
    return DemoRequest(
        user_id=None,
        text=text,
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
        session_key=session_key,
    )


def _backend_with_mock_executor() -> tuple[LiveBackend, MagicMock, list]:
    """LiveBackend với PlanExecutor giả lập: run() ghi 1 turn vào session đang gắn.

    Trả (backend, executor, seen_sessions) — seen_sessions ghi lại object
    executor.session tại thời điểm run() để assert attach/reset.
    """
    backend = LiveBackend()
    backend._initialized = True

    executor = MagicMock()
    executor.reflect_rounds = 0
    executor.last_plan, executor.last_question = [], None
    executor.last_reflections, executor.last_first_attempt_ok, executor.last_truncated = 0, True, False
    executor.last_usage = {}

    seen_sessions: list = []

    def fake_run(text: str):
        seen_sessions.append(executor.session)
        if executor.session is not None:
            executor.session.add_turn(text, "[]", "")
        return []

    executor.run.side_effect = fake_run
    backend._executor_planner = executor
    backend._executor_planner_memory = executor
    return backend, executor, seen_sessions


@pytest.fixture
def patched_demo(monkeypatch):
    monkeypatch.setattr(module, "compose_answer", lambda *a, **k: MagicMock())
    monkeypatch.setattr(
        module,
        "adapt_from_inference",
        lambda *a, **k: DemoResult(status="ok", text="t", items=[], trace=None, usage={}, error=None),
    )


def test_session_turns_increment_over_three_turns(patched_demo):
    backend, executor, _ = _backend_with_mock_executor()

    results = [backend.respond(_request(f"turn {i}", session_key="conv1")) for i in range(3)]

    assert [r.session_turns for r in results] == [1, 2, 3]
    session = backend._sessions["conv1"]
    assert len(session.turns) == 3
    assert [t.user_request for t in session.turns] == ["turn 0", "turn 1", "turn 2"]
    assert executor.session is None  # reset sau mỗi request


def test_new_key_creates_isolated_conversation(patched_demo):
    backend, _, _ = _backend_with_mock_executor()

    backend.respond(_request("a1", session_key="convA"))
    backend.respond(_request("a2", session_key="convA"))
    r_b = backend.respond(_request("b1", session_key="convB"))

    assert r_b.session_turns == 1  # convB bắt đầu từ 0, không thừa hưởng convA
    assert len(backend._sessions["convA"].turns) == 2
    assert len(backend._sessions["convB"].turns) == 1
    assert backend._sessions["convA"] is not backend._sessions["convB"]


def test_two_keys_do_not_share_state(patched_demo):
    backend, executor, seen = _backend_with_mock_executor()

    backend.respond(_request("a1", session_key="convA"))
    backend.respond(_request("b1", session_key="convB"))
    backend.respond(_request("a2", session_key="convA"))

    sess_a, sess_b = backend._sessions["convA"], backend._sessions["convB"]
    assert [t.user_request for t in sess_a.turns] == ["a1", "a2"]
    assert [t.user_request for t in sess_b.turns] == ["b1"]
    # Mỗi run() nhìn thấy đúng Session của key mình, không phải của key kia
    assert seen[0] is sess_a and seen[1] is sess_b and seen[2] is sess_a
    assert executor.session is None


def test_sessions_lru_eviction(monkeypatch):
    """_sessions giới hạn max_sessions: evict key cũ nhất, key vừa dùng được giữ."""
    from types import SimpleNamespace

    monkeypatch.setattr(
        module, "get_demo_limits",
        lambda: SimpleNamespace(max_sessions=2, max_error_length=300),
    )
    backend = LiveBackend()

    def key(k: str) -> DemoRequest:
        return _request("x", session_key=k)

    backend._session_for(key("k1"))
    s_k2 = backend._session_for(key("k2"))
    backend._session_for(key("k3"))  # evict k1 (cũ nhất)
    assert set(backend._sessions) == {"k2", "k3"}

    assert backend._session_for(key("k2")) is s_k2  # refresh k2 -> k3 thành cũ nhất
    backend._session_for(key("k4"))  # evict k3
    assert set(backend._sessions) == {"k2", "k4"}
    assert backend._session_for(key("k2")) is s_k2


def test_no_key_is_single_turn(patched_demo):
    backend, executor, seen = _backend_with_mock_executor()

    r1 = backend.respond(_request("solo 1"))
    r2 = backend.respond(_request("solo 2"))

    assert r1.session_turns is None
    assert r2.session_turns is None
    assert seen == [None, None]  # executor.session là None trong run()
    assert backend._sessions == {}  # không tạo Session nào
    assert executor.session is None
