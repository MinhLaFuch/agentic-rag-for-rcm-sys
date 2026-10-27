"""Explicit, deterministic intent search; no inferred preferences or LLM calls."""
import re
import time
import math
from numbers import Real

from package.config import load_config
from package.tools.base import check_top_k, ToolInputError


def recommend_from_intent(search_tool, query_tool, query, *, filters=None, seen_items=(), top_k=10):
    """Preserve BM25 order and hard filters; fetch complete metadata or fail closed.

    Keywords are an explicit user input, not a parsed natural-language request.
    No popularity fallback or CF reranking is applied to an intent-only result.
    The returned trace records every attempted tool call, including failures.
    """
    steps=[]
    plan=[]
    def outcome(status, *, items=None, error=None, question=None):
        return dict(status=status,items=items or [],error=error,question=question,
                    source="intent_bm25",steps=steps,plan=plan)
    if not isinstance(query,str) or not query.strip():
        return outcome("ask_user",question="Bạn muốn tìm sản phẩm gì? Hãy điền từ khóa sản phẩm và bộ lọc giá nếu cần.")
    if re.search(r"[$€₫]|(?:under|below|over|above|between|less than|more than|at most|at least|up to|maximum|minimum)\s*[-+]?\d|[<>]\s*\d|\b\d+(?:\.\d+)?\s*(?:usd|eur|vnd|dollars)\b|\b(?:usd|eur|vnd)\s*\d",query,re.I):
        return outcome("ask_user",question="Hãy để từ khóa chỉ mô tả sản phẩm và điền điều kiện giá vào bộ lọc riêng (USD).")
    if filters is not None and not isinstance(filters,dict):
        return outcome("tool_error",error="filters must be a dictionary")
    maximum=int(load_config("agent/tools")["tools"]["max_query_rows"])
    try:
        top_k=check_top_k(top_k,upper=maximum,name="top_k")
    except ToolInputError as exc:
        return outcome("tool_error",error=str(exc))
    effective=dict(filters or {})
    for key in ("price_min","price_max"):
        value=effective.get(key)
        if value is not None and (isinstance(value,bool) or not isinstance(value,Real) or not math.isfinite(value) or value<0):
            return outcome("tool_error",error=f"{key} must be a finite non-negative USD amount")
    excluded=effective.get("exclude_item_ids",[])
    if not isinstance(excluded,(list,tuple)) or any(not isinstance(i,str) for i in excluded):
        return outcome("tool_error",error="exclude_item_ids must be a list of item IDs")
    effective["exclude_item_ids"]=list(dict.fromkeys([*excluded,*seen_items]))

    def call(tool,**args):
        plan.append({"tool":tool.name,"args":args})
        start=time.perf_counter()
        try:
            result=tool(**args)
            row=dict(tool=tool.name,ok=result.ok,data=result.data,error=result.error)
        except Exception as exc:
            row=dict(tool=tool.name,ok=False,data={},error=f"{type(exc).__name__}: {exc}")
        row["latency_seconds"]=time.perf_counter()-start
        steps.append(row)
        return row

    retrieved=call(search_tool,query=query.strip(),filters=effective,limit=top_k)
    if not retrieved["ok"]:
        return outcome("tool_error",error=retrieved["error"])
    candidates=retrieved["data"]["candidates"]
    ids=list(dict.fromkeys(r["item_id"] for r in candidates))[:top_k]
    if not ids:
        return outcome("no_result")
    fetched=call(query_tool,item_ids=ids,max_rows=len(ids))
    if not fetched["ok"]:
        return outcome("tool_error",error=fetched["error"])
    rows=fetched["data"]["items"]
    metadata={r["item_id"]:r for r in rows}
    if len(rows)!=len(metadata) or set(metadata)!=set(ids):
        error="Missing, duplicate or unexpected fetched metadata"
        steps[-1].update(ok=False,error=error)
        return outcome("tool_error",error=error)
    return outcome("ok",items=[metadata[i] for i in ids])
