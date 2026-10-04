"""
End-to-end smoke test cho Phase 1 (mục XXIV): xác nhận toàn bộ chuỗi
config -> factory -> provider hoạt động được từ đầu đến cuối, không
chỉ test từng unit riêng lẻ.
"""

from package.config.loader import load_config
from package.llm.base import LLMMessage
from package.llm.factory import build_llm_provider


def test_end_to_end_agent_config_to_llm_call(monkeypatch):
    # 1. Load config thật từ configs/llm.yaml (không mock config)
    llm_config = load_config("llm")
    reranking_config = load_config("reranking")

    # 2. Build provider qua factory (đúng nguyên tắc mục XXI: business
    #    logic không tự import provider cụ thể)
    provider = build_llm_provider(llm_config)

    # 3. Gọi thử một request tối giản, mô phỏng bước Reranking (mục XIV)
    response = provider.complete(
        [LLMMessage(role="user", content="rerank top candidates")],
        response_format_json=reranking_config["require_json_output"],
    )

    assert response.text
    assert response.provider_name == "mock"


def test_end_to_end_data_config():
    domains_config = load_config("domains")
    semantic_retrieval_config = load_config("semantic_retrieval")
    experiments_config = load_config("experiments")

    # Domain đến từ domains.yaml, không hard-code trong logic (mục V, XX)
    assert domains_config["domains"][0]["name"] == "Video_Games"
    # Constraint chống context overload phải tồn tại (mục X, XIV)
    assert semantic_retrieval_config["semantic_retrieval"]["max_context_items"] <= 20
    # Experiment matrix phải có đủ 10 cấu hình theo kế hoạch Phase 0
    assert len(experiments_config["experiments"]) == 10
