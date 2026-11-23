"""Step 2b: generate Vietnamese probe queries + English translations via LLM.

For each probe item, ask the LLM for ONE natural Vietnamese shopping request
describing the item WITHOUT copying its English title (style = real campaign
requests). Then translate each VI query to English. Also translates the 152
real campaign request texts (for Step 3).

Resumable: appends per-batch JSONL; re-run skips completed batches.

Outputs:
  investigations/vi_retrieval/vi_queries.jsonl   (item_id, vi_query, en_query)
  investigations/vi_retrieval/request_translations.jsonl (request_id, vi_text, en_text)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from package.api import LLMMessage, build_llm_provider  # noqa: E402
from package.config import load_config  # noqa: E402

BATCH = 10
REQUESTS_JSONL = ROOT / ("experiments/agent_eval/campaigns/campaign_005/"
                         "exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/"
                         "requests.jsonl")

EXEMPLARS = [
    'Tôi là user ..., vừa mua <item>. Gợi ý cho tôi 10 sản phẩm tương tự.',
    'Tôi là user ..., mới đến và chưa mua gì. Tôi muốn tìm 10 sản phẩm thuộc nhóm "Baby Floats".',
    "Tôi là user .... Gợi ý cho tôi 10 sản phẩm hợp với thói quen mua hàng của tôi.",
    'Tôi là user .... Gợi ý cho tôi 10 sản phẩm giá dưới 300k, ưu tiên đồ điện tử.',
    "Gợi ý cho tôi sản phẩm hay.",
]


def llm():
    return build_llm_provider(load_config("agent/llm"))


def chat(provider, system: str, user: str, max_tokens: int = 2000) -> str:
    for attempt in range(3):
        try:
            r = provider.complete(
                [LLMMessage(role="system", content=system),
                 LLMMessage(role="user", content=user)],
                temperature=0.7, max_tokens=max_tokens)
            return r.text
        except Exception as exc:  # noqa: BLE001
            print(f"  llm error attempt {attempt}: {exc}", file=sys.stderr, flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("LLM failed 3x")


def gen_vi_queries(provider, probe: pd.DataFrame) -> None:
    out_path = OUT / "vi_queries.jsonl"
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["item_id"])
    todo = probe[~probe["item_id"].isin(done)]
    print(f"VI queries: {len(done)} done, {len(todo)} todo", flush=True)

    system = (
        "You write realistic Vietnamese e-commerce shopping requests for an "
        "Amazon-like catalog. For EACH item below, write ONE natural Vietnamese "
        "request a shopper would type, describing what they want WITHOUT copying "
        "the English product title or brand words. Vary phrasing like these "
        "examples:\n" + "\n".join(f"- {e}" for e in EXEMPLARS) +
        "\nReply with JSON only: {\"queries\": [{\"item_id\": \"...\", \"vi_query\": \"...\"}, ...]}"
    )
    rows = list(todo.itertuples(index=False))
    with out_path.open("a", encoding="utf-8") as f:
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            payload = [{"item_id": r.item_id, "title": r.title,
                        "main_category": r.main_category,
                        "categories": list(r.categories)[:4]} for r in batch]
            user = "Items:\n" + json.dumps(payload, ensure_ascii=False, indent=1)
            text = chat(provider, system, user)
            try:
                data = json.loads(text[text.index("{"):text.rindex("}") + 1])
                for q in data["queries"]:
                    f.write(json.dumps(q, ensure_ascii=False) + "\n")
                f.flush()
            except Exception as exc:  # noqa: BLE001
                print(f"  batch {i//BATCH} parse fail: {exc}\n{text[:300]}", file=sys.stderr, flush=True)
            print(f"  VI batch {i//BATCH + 1}/{(len(rows)+BATCH-1)//BATCH}", flush=True)


def translate_vi(provider, items: list[dict], out_name: str, id_key: str, text_key: str,
                 faithful: bool = False) -> None:
    out_path = OUT / out_name
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)[id_key])
    todo = [x for x in items if x[id_key] not in done]
    print(f"{out_name}: {len(done)} translated, {len(todo)} todo", flush=True)
    if faithful:
        instruction = ("Translate each Vietnamese e-commerce request faithfully into "
                       "English. Preserve meaning, names, numbers and category phrases. "
                       "Reply JSON only: {\"translations\": [{\"id\": \"...\", \"en\": \"...\"}, ...]}")
    else:
        instruction = ("Translate each Vietnamese e-commerce request into natural English "
                       "search keywords/phrases a shopper would use. Keep it short "
                       "(2-8 words). Reply JSON only: {\"translations\": [{\"id\": \"...\", \"en\": \"...\"}, ...]}")
    system = instruction
    with out_path.open("a", encoding="utf-8") as f:
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            payload = [{"id": x[id_key], "vi": x[text_key]} for x in batch]
            text = chat(provider, system, json.dumps(payload, ensure_ascii=False))
            try:
                data = json.loads(text[text.index("{"):text.rindex("}") + 1])
                for q in data["translations"]:
                    q[id_key] = q.pop("id", None)
                    f.write(json.dumps(q, ensure_ascii=False) + "\n")
                f.flush()
            except Exception as exc:  # noqa: BLE001
                print(f"  translate batch {i//BATCH} parse fail: {exc}", file=sys.stderr, flush=True)
            print(f"  translate batch {i//BATCH + 1}/{(len(todo)+BATCH-1)//BATCH}", flush=True)


def main() -> None:
    probe = pd.read_parquet(OUT / "probe_items.parquet")
    provider = llm()

    gen_vi_queries(provider, probe)

    # translate probe VI queries
    vi = [json.loads(l) for l in (OUT / "vi_queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    vi_items = [{"item_id": q["item_id"], "vi_query": q["vi_query"]} for q in vi]
    # reuse translate via item_id/vi_query keys
    out_path = OUT / "vi_query_translations.jsonl"
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["item_id"])
    todo = [x for x in vi_items if x["item_id"] not in done]
    print(f"probe translations: {len(done)} done, {len(todo)} todo", flush=True)
    system = ("Translate each Vietnamese e-commerce request into natural English "
              "search keywords/phrases a shopper would use. Keep it short "
              "(2-8 words). Reply JSON only: {\"translations\": [{\"item_id\": \"...\", \"en_query\": \"...\"}, ...]}")
    with out_path.open("a", encoding="utf-8") as f:
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            payload = [{"item_id": x["item_id"], "vi": x["vi_query"]} for x in batch]
            text = chat(provider, system, json.dumps(payload, ensure_ascii=False))
            try:
                data = json.loads(text[text.index("{"):text.rindex("}") + 1])
                for q in data["translations"]:
                    f.write(json.dumps(q, ensure_ascii=False) + "\n")
                f.flush()
            except Exception as exc:  # noqa: BLE001
                print(f"  translate batch {i//BATCH} parse fail: {exc}", file=sys.stderr, flush=True)
            print(f"  translate batch {i//BATCH + 1}/{(len(todo)+BATCH-1)//BATCH}", flush=True)

    # translate the 152 real request texts
    reqs = []
    if REQUESTS_JSONL.exists():
        with REQUESTS_JSONL.open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                reqs.append({"request_id": r.get("request_id") or r.get("id"), "text": r.get("text") or r.get("request")})
    translate_vi(provider, reqs, "request_translations.jsonl", "request_id", "text", faithful=True)


if __name__ == "__main__":
    main()
