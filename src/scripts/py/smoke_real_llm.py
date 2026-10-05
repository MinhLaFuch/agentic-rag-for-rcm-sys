"""Smoke test: PlanExecutor + 5 tool trên fixture synthetic, dùng LLM thật theo configs/llm.yaml.

Chạy từ src/:  python scripts/py/smoke_real_llm.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd

from package.agents import PlanExecutor
from package.config.loader import load_config
from package.llm import build_llm_provider
from package.llm._error import LLMProviderError
from package.memory.memory_tool import MemoryTool
from package.tools import BaselineScorer, ItemCFTool, ItemCorpus, QueryTool, RecoModelTool, SemanticSearchTool
from package.tools.recommenders import ItemKNNRecommender

MAX_TOKENS = 2048  # ngân sách token cho 1 lần plan (model reasoning ăn token suy luận vào đây)
PRINT_DATA_CHARS = 300  # cắt data từng step khi in để log gọn

REQUESTS = [  # user_id / item_id phải có trong fixture bên dưới
    "Tôi là user u2, vừa mua Video_Games::vg_a. Gợi ý cho tôi vài sản phẩm tương tự.",
    "Tôi là user u2. Tóm tắt thói quen mua hàng của tôi, rồi tìm cho tôi phụ kiện game giá dưới 20 đô.",
    "Gợi ý cho tôi sản phẩm hay.",  # cố tình thiếu thông tin: mong plan rỗng hoặc lỗi rõ ràng, không bịa id
]


def build_fixture() -> list:
    # Cùng dữ liệu với tests/tools_helpers.py; thay bằng load data thật khi sang bước 2
    meta = pd.DataFrame({
        "parent_asin": ["vg_a", "vg_b", "vg_c", "el_a", "el_d"],
        "domain": ["Video_Games"] * 3 + ["Electronics"] * 2,
        "title": ["Super Video Game", "Mario 100%", "Game Accessories", "Electronics Accessory", "Electronics Device"],
        "price": [19.99, None, 5.5, 25.99, 12.99],
        "average_rating": [4.5, 4.6, 4.2, 4.3, 4.3],
        "rating_number": [200, 150, 15, 40, 5],
        "store": ["Amazon", "Amazon", "Acme", "Amazon", "Acme"],
        "categories": [["Video Games", "Games"], ["Video Games", "Games"], ["Accessories"],
                       ["Accessories", "Electronics"], ["Accessories", "Electronics"]],
    })
    corpus = ItemCorpus.from_dataframe(meta)

    vg_a, vg_b, el_a, el_d = "Video_Games::vg_a", "Video_Games::vg_b", "Electronics::el_a", "Electronics::el_d"
    interactions = pd.DataFrame({
        "user_id": ["u1", "u1", "u2", "u2", "u2", "u3", "u4", "u4", "u5", "u5", "u6", "u7", "u7", "u8", "u9", "u10", "u13"],
        "item_id": [vg_a, el_a, vg_a, vg_b, vg_b, vg_a, vg_a, el_a, vg_b, vg_a, el_d, el_d, el_a, el_d, vg_a, vg_a, el_a],
    })
    user2id = {u: i for i, u in enumerate(interactions["user_id"].unique())}
    item2id = {it: i for i, it in enumerate(interactions["item_id"].unique())}
    interactions["user_idx"] = interactions["user_id"].map(user2id)
    interactions["item_idx"] = interactions["item_id"].map(item2id)

    knn = ItemKNNRecommender(5).fit(interactions)
    scorer = BaselineScorer(knn)
    return [  # 1 chỗ duy nhất liệt kê tool agent được dùng
        ItemCFTool(knn, item2id, corpus=corpus),
        RecoModelTool(scorer, user2id, item2id, corpus=corpus),
        QueryTool(corpus),
        SemanticSearchTool(corpus),
        MemoryTool(interactions, user2id, item2id, corpus),
    ]


def main() -> None:
    llm = build_llm_provider(load_config("llm"))
    print(f"Provider: {llm.provider_name}  health: {llm.health_check()}")
    executor = PlanExecutor(llm, build_fixture(), max_tokens=MAX_TOKENS)

    for request in REQUESTS:
        print("\n" + "=" * 72 + f"\nREQUEST: {request}")
        start = time.monotonic()
        try:
            results = executor.run(request)
        except (ValueError, LLMProviderError) as exc:
            print(f"PLAN FAILED ({time.monotonic() - start:.1f}s): {exc}")
            continue
        elapsed = time.monotonic() - start

        print("PLAN:", json.dumps(executor.last_plan, ensure_ascii=False))
        if executor.last_question:
            print("ASK_USER:", executor.last_question)
        for i, r in enumerate(results, 1):
            data = json.dumps(r["data"], ensure_ascii=False, default=str)[:PRINT_DATA_CHARS]
            print(f"  [{i}] {r['tool']}  ok={r['ok']}  error={r['error']}\n      data={data}")
        resp = executor.last_response
        print(f"LLM latency={resp.latency_seconds:.1f}s  tokens(prompt/completion)="
              f"{resp.prompt_tokens}/{resp.completion_tokens}  total={elapsed:.1f}s")


if __name__ == "__main__":
    main()