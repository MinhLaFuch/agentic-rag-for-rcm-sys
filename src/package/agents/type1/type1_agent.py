"""
Type1Agent — agent-assisted recommender, plan cố định, không LLM.

Thứ tự cố định: retrieve (ItemCFTool) -> rank (RecoModelTool) -> fetch (QueryTool).
LLM ranking để dành làm "improvement room" sau (đã quyết định), bản này chỉ ráp
lại 3 tool đã test trong tests/tools — không có logic mới cần tin.
"""
from __future__ import annotations

from typing import Any

from ...tools.ranking.item_cf_tool import ItemCFTool
from ...tools.ranking.reco_model_tool import RecoModelTool
from ...tools.sql_query.query_tool import QueryTool
from .._limits import get_agent_limits


class Type1Agent:
    def __init__(self, itemcf_tool: ItemCFTool, reco_tool: RecoModelTool, query_tool: QueryTool) -> None:
        self.itemcf_tool = itemcf_tool
        self.reco_tool = reco_tool
        self.query_tool = query_tool
        self.last_tool_calls: list[dict[str, Any]] = []

    def recommend(self, user_id: str, seed_items: list[str], top_k: int = 10) -> dict[str, Any]:
        self.last_tool_calls = []

        def call(tool, action, **kwargs):
            start = len(tool.logger.records)
            try:
                return tool(agent="type1", action=action, **kwargs)
            finally:
                self.last_tool_calls.extend(dict(row) for row in tool.logger.records[start:])

        # 1. Retrieve — candidate quanh các item user vừa tương tác (seed_items)
        limits = get_agent_limits()
        retrieved = call(self.itemcf_tool, "retrieve",
            items=seed_items, top_k=max(top_k * limits.type1_candidate_multiplier, limits.type1_min_candidates)
        )
        if not retrieved.ok:
            return {"ok": False, "stage": "retrieve", "error": retrieved.error}
        candidates = [c["item_id"] for c in retrieved.data["candidates"]]
        if not candidates:
            return {"ok": False, "stage": "retrieve", "error": "no candidates returned"}

        # 2. Rank — RecoModelTool xếp hạng lại candidate bằng model (không LLM)
        ranked = call(self.reco_tool, "rank", user_id=user_id, candidates=candidates, top_k=top_k)
        if not ranked.ok:
            return {"ok": False, "stage": "rank", "error": ranked.error}
        top_ids = [r["item_id"] for r in ranked.data["ranked"]]
        if not top_ids:
            return {"ok": True, "items": [], "cold_start": ranked.data["cold_start"]}

        # 3. Fetch — title/metadata cho output cuối
        fetched = call(self.query_tool, "fetch", item_ids=top_ids)
        if not fetched.ok:
            return {"ok": False, "stage": "fetch", "error": fetched.error}

        meta_by_id = {row["item_id"]: row for row in fetched.data["items"]}
        items = [
            {**r, **meta_by_id.get(r["item_id"], {})}
            for r in ranked.data["ranked"]
        ]
        return {"ok": True, "items": items, "cold_start": ranked.data["cold_start"]}
