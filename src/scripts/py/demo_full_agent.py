"""
Demo: đăng ký đủ 5 tool vào PlanExecutor (LLM <-> tools <-> data qua memory).
Dùng build_llm_provider(load_config("llm")) để tạo provider từ configs/llm.yaml.
Khi có LLM_API_KEY và endpoint thật, chạy script này trực tiếp với data thật.
"""
from __future__ import annotations

from package.agents.plan_executor import PlanExecutor
from package.config.loader import load_config
from package.llm.factory import build_llm_provider
from package.memory.memory_tool import MemoryTool
from package.tools.ranking.item_cf_tool import ItemCFTool
from package.tools.ranking.reco_model_tool import RecoModelTool
from package.tools.retrieval.semantic_search_tool import SemanticSearchTool
from package.tools.sql_query.query_tool import QueryTool


def build_tools(knn, scorer, user2id, item2id, interactions, corpus):
    # 1 chỗ duy nhất liệt kê tool nào agent được dùng — thêm/bớt tool chỉ sửa ở đây
    return [
        ItemCFTool(knn, item2id, corpus=corpus),
        RecoModelTool(scorer, user2id, item2id, corpus=corpus),
        QueryTool(corpus),
        SemanticSearchTool(corpus),
        MemoryTool(interactions, user2id, item2id, corpus),
    ]


def build_executor(llm, tools) -> PlanExecutor:
    return PlanExecutor(llm, tools)


if __name__ == "__main__":
    # Thay phần này bằng load data thật (resource/splits/..., ItemCorpus.from_parquet(...))
    # khi chạy trên data thật — đây chỉ để chứng minh wiring chạy được.
    raise SystemExit(
        "Demo module — import build_tools()/build_executor() vào script có data thật, "
        "đừng chạy trực tiếp file này."
    )
