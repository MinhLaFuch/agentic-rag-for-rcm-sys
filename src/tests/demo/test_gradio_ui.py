"""Test cho giao diện Gradio (Giai đoạn 2)."""

import pytest

gradio = pytest.importorskip("gradio")

from package.demo import MockBackend, DemoRequest, DemoProfile


def test_build_ui_with_mock_backend():
    """Dựng UI với MockBackend không được crash."""
    from scripts.demo.run_demo import build_ui

    backend = MockBackend()
    profiles = backend.get_profiles()
    demo = build_ui(backend, mock_mode=True, profiles=profiles, default_inference_mode="llm")

    assert demo is not None
    assert hasattr(demo, "blocks")


def test_submit_handler_with_mock_backend():
    """Test backend trực tiếp (UI handler được test qua Gradio riêng)."""
    backend = MockBackend()

    request = DemoRequest(
        user_id="user123",
        text="Gợi ý sản phẩm",
        reflect_rounds=0,
        use_memory=False,
        mode="planner",
        inference_mode="llm",
    )
    result = backend.respond(request)
    assert result.status in {"ok", "ask_user", "no_result", "tool_error"}
    assert isinstance(result.text, str)
    assert isinstance(result.items, list)
    # Check memory field exists
    assert result.memory is not None


def test_gradio_import_error_handling():
    """Test kiểm tra import gradio khi thiếu."""
    # Test này chỉ để verify pytest.importorskip hoạt động
    # Nếu gradio không được cài, test sẽ bị skip
    assert gradio is not None


def test_build_ui_with_profiles():
    """Dựng UI với profiles không được crash."""
    from scripts.demo.run_demo import build_ui

    backend = MockBackend()
    profiles = backend.get_profiles()
    demo = build_ui(backend, mock_mode=True, profiles=profiles, default_inference_mode="template")

    assert demo is not None
    assert hasattr(demo, "blocks")


def test_mock_backend_get_profiles():
    """MockBackend.get_profiles phải trả về list DemoProfile."""
    backend = MockBackend()
    profiles = backend.get_profiles()

    assert isinstance(profiles, list)
    assert len(profiles) >= 1
    assert all(isinstance(p, DemoProfile) for p in profiles)
    # Check blank profile exists
    blank_profiles = [p for p in profiles if p.profile_id == "blank"]
    assert len(blank_profiles) == 1
    assert blank_profiles[0].user_id is None
