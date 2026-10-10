"""
End-to-end smoke test cho Phase 1 (mục XXIV): xác nhận toàn bộ chuỗi
config -> factory -> provider hoạt động được từ đầu đến cuối, không
chỉ test từng unit riêng lẻ.

HTTP request được chặn bởi một fake urlopen — không cần endpoint thật,
không gọi mạng, test luôn chạy được trong CI.
"""

import io
import json
import urllib.request

from package.config.loader import load_config
from package.llm.base import LLMMessage
from package.llm.factory import build_llm_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_chat_response(content: str) -> bytes:
    """Minimal OpenAI-compatible chat/completions response body."""
    return json.dumps(
        {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 16},
        }
    ).encode("utf-8")


class _FakeHTTPResponse:
    """Mimics the file-like object returned by urllib.request.urlopen."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_end_to_end_agent_config_to_llm_call(monkeypatch):
    # 1. Load config thật từ configs/agent/llm.yaml (provider: openai_compatible); base_url đến từ biến môi trường
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8000/v1")
    llm_config = load_config("agent/llm")

    # 2. Patch urllib so no real HTTP call is made
    fake_reply = _fake_chat_response(
        '{"item_id": "B001", "score": 0.9, "reasons": ["smoke test"]}'
    )
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeHTTPResponse(fake_reply),
    )

    # 3. Build provider qua factory (đúng nguyên tắc mục XXI)
    provider = build_llm_provider(llm_config)

    # 4. Gọi thử một request tối giản, mô phỏng bước Reranking (mục XIV)
    response = provider.complete(
        [LLMMessage(role="user", content="rerank top candidates")],
        response_format_json=True,
    )

    assert response.text
    assert response.provider_name == "openai_compatible"
    assert response.latency_seconds is not None


def test_end_to_end_data_config():
    domains_config = load_config("path/domains")

    # Domain đến từ domains.yaml, không hard-code trong logic (mục V, XX)
    assert domains_config["domains"][0]["name"] == "Video_Games"
