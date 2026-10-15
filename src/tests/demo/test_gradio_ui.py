"""Test cho giao diện Gradio (Giai đoạn 2)."""

import pytest

gradio = pytest.importorskip("gradio")

from package.demo import MockBackend, DemoRequest


def test_build_ui_with_mock_backend():
    """Dựng UI với MockBackend không được crash."""
    from scripts.run_demo import build_ui

    backend = MockBackend()
    demo = build_ui(backend, mock_mode=True, sample_user_dict=None)

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
    )
    result = backend.respond(request)
    assert result.status in {"ok", "ask_user", "no_result", "tool_error"}
    assert isinstance(result.text, str)
    assert isinstance(result.items, list)


def test_gradio_import_error_handling():
    """Test kiểm tra import gradio khi thiếu."""
    # Test này chỉ để verify pytest.importorskip hoạt động
    # Nếu gradio không được cài, test sẽ bị skip
    assert gradio is not None


def test_build_ui_with_sample_users():
    """Dựng UI với sample_user_dict không được crash."""
    from scripts.run_demo import build_ui

    backend = MockBackend()
    sample_user_dict = {
        "cold": ["user1", "user2"],
        "sparse": ["user3"],
        "warm": ["user4", "user5", "user6"],
    }
    demo = build_ui(backend, mock_mode=True, sample_user_dict=sample_user_dict)

    assert demo is not None
    assert hasattr(demo, "blocks")
