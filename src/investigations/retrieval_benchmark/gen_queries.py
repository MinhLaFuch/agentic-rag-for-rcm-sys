"""Generate descriptive Vietnamese queries for the 196 held-out targets + EN translations.

Style follows investigations/vi_retrieval/step2b_gen_queries.py: ONE natural VI
shopping request per item, describing it WITHOUT copying the English title.
Resumable JSONL append; re-run skips completed item_ids.

Outputs:
  target_queries.jsonl      {item_id, vi_query}
  target_query_translations.jsonl  {item_id, en_query}
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

EXEMPLARS = [
    "Tôi muốn tìm tai nghe chụp tai chống ồn để đi làm mỗi ngày.",
    "Cần một cái loa bluetooth nhỏ gọn, pin dùng được cả ngày.",
    "Tôi đang tìm đồ chơi xếp hình cho bé khoảng 3 tuổi.",
    "Cho tôi xin gợi ý bàn phím cơ không dây tầm giá 1-2 triệu.",
    "Cần mua ổ cứng ngoài để backup ảnh, dung lượng lớn.",
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


def parse_json(text: str):
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def gen_vi(provider, df: pd.DataFrame) -> None:
    out_path = OUT / "target_queries.jsonl"
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["item_id"])
    todo = df[~df["item_id"].isin(done)]
    print(f"VI queries: {len(done)} done, {len(todo)} todo", flush=True)

    system = (
        "You write realistic Vietnamese e-commerce shopping requests for an "
        "Amazon-like catalog. For EACH item below, write ONE natural Vietnamese "
        "request a shopper would type, describing what they want WITHOUT copying "
        "the English product title, brand names, or model numbers. Vary phrasing "
        "like these examples:\n" + "\n".join(f"- {e}" for e in EXEMPLARS) +
        "\nReply with JSON only: {\"queries\": [{\"item_id\": \"...\", \"vi_query\": \"...\"}, ...]}"
    )
    rows = list(todo.itertuples(index=False))
    with out_path.open("a", encoding="utf-8") as f:
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            payload = [{"item_id": r.item_id, "title": r.title,
                        "main_category": r.main_category,
                        "categories": list(r.categories)[:4], "price": r.price} for r in batch]
            text = chat(provider, system, "Items:\n" + json.dumps(payload, ensure_ascii=False, indent=1))
            try:
                for q in parse_json(text)["queries"]:
                    f.write(json.dumps(q, ensure_ascii=False) + "\n")
                f.flush()
            except Exception as exc:  # noqa: BLE001
                print(f"  batch {i//BATCH} parse fail: {exc}\n{text[:300]}", file=sys.stderr, flush=True)
            print(f"  VI batch {i//BATCH + 1}/{(len(rows)+BATCH-1)//BATCH}", flush=True)


def translate(provider, vi: list[dict]) -> None:
    out_path = OUT / "target_query_translations.jsonl"
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["item_id"])
    todo = [x for x in vi if x["item_id"] not in done]
    print(f"EN translations: {len(done)} done, {len(todo)} todo", flush=True)

    system = ("Translate each Vietnamese e-commerce request into natural English "
              "search keywords/phrases a shopper would use. Keep it short "
              "(2-8 words). Reply JSON only: "
              "{\"translations\": [{\"item_id\": \"...\", \"en_query\": \"...\"}, ...]}")
    with out_path.open("a", encoding="utf-8") as f:
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            user = "Queries:\n" + json.dumps(batch, ensure_ascii=False, indent=1)
            text = chat(provider, system, user)
            try:
                for t in parse_json(text)["translations"]:
                    f.write(json.dumps(t, ensure_ascii=False) + "\n")
                f.flush()
            except Exception as exc:  # noqa: BLE001
                print(f"  batch {i//BATCH} parse fail: {exc}\n{text[:300]}", file=sys.stderr, flush=True)
            print(f"  EN batch {i//BATCH + 1}/{(len(todo)+BATCH-1)//BATCH}", flush=True)


def main() -> None:
    provider = llm()
    df = pd.read_parquet(OUT / "targets.parquet")
    items = df.drop_duplicates("item_id")[["item_id", "title", "main_category", "categories", "price"]]
    items["categories"] = items["categories"].apply(lambda c: list(c) if c is not None else [])

    gen_vi(provider, items)

    vi = [json.loads(l) for l in (OUT / "target_queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    translate(provider, vi)
    print("done", flush=True)


if __name__ == "__main__":
    sys.exit(main())
