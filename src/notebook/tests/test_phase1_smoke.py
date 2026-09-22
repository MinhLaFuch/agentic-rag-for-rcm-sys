"""
End-to-end smoke test cho Phase 1 (mục XXIV): xác nhận toàn bộ chuỗi
config -> factory -> provider hoạt động được từ đầu đến cuối, không
chỉ test từng unit riêng lẻ.
"""

from agent.config.loader import load_config
from agent.llm.base import LLMMessage
from agent.llm.factory import build_llm_provider


def test_end_to_end_agent_config_to_llm_call(monkeypatch):
    # 1. Load config thật từ configs/agent.yaml (không mock config)
    agent_config = load_config("agent")

    # 2. Build provider qua factory (đúng nguyên tắc mục XXI: business
    #    logic không tự import provider cụ thể)
    provider = build_llm_provider(agent_config)

    # 3. Gọi thử một request tối giản, mô phỏng bước Reranking (mục XIV)
    response = provider.complete(
        [LLMMessage(role="user", content="rerank top candidates")],
        response_format_json=agent_config["reranking"]["require_json_output"],
    )

    assert response.text
    assert response.provider_name == "mock"


def test_end_to_end_data_config_with_domain(monkeypatch):
    monkeypatch.setenv("DOMAIN", "Video_Games")
    data_config = load_config("data")
    retrieval_config = load_config("retrieval")
    evaluation_config = load_config("evaluation")

    # Domain phải propagate đúng, không hard-code (mục V, XX)
    assert data_config["domain"] == "Video_Games"
    # Constraint chống context overload phải tồn tại (mục X, XIV)
    assert retrieval_config["semantic_retrieval"]["max_context_items"] <= 20
    # Experiment matrix phải có đủ 10 cấu hình theo kế hoạch Phase 0
    assert len(evaluation_config["experiment_matrix"]) == 10
