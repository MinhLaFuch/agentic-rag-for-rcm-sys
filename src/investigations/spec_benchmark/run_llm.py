"""Phase-3 LLM runner: paraphrase / leakcheck / extract over gold_specs.jsonl.

Resumable: appends to JSONL and skips request_ids already present, so a killed
run never double-pays. All calls go through OpenAICompatibleProvider
(configs/agent/llm.yaml model = gpt-5.5) with temperature 0.

Usage:
  python investigations/spec_benchmark/run_llm.py paraphrase --limit 10
  python investigations/spec_benchmark/run_llm.py leakcheck
  python investigations/spec_benchmark run extract

Env: LLM_BASE_URL, LLM_API_KEY (never written to disk).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from package.api.llm_provider import LLMMessage  # noqa: E402
from package.api.openai_compatible_provider import OpenAICompatibleProvider  # noqa: E402

GOLD = Path("investigations/spec_benchmark/gold_specs.jsonl")
OUT = Path("investigations/spec_benchmark")
MODEL = "gpt-5.5"

PARAPHRASE_TYPES = ["en", "vi_paraphrase", "code_mix", "underspecified"]

EXTRACT_SYSTEM = """You are a query distiller for an e-commerce recommendation agent.
Read the user's request and output ONE JSON object — a structured spec of what
the user wants. No prose, no markdown fences.

Fields (all required; use null when absent):
- kind: one of "similar" (user references a purchased item and wants similar),
  "personalized" (generic recommendation from history), "constrained"
  (explicit category+price/rating limits), "cold_text" (browse a named
  product category), "exclusion" (explicitly excludes item(s)/category),
  "ambiguous" (too vague to act on), "unanswerable" (cannot be served),
  "descriptive" (describes a specific desired item), "unknown".
- category_coarse: broad department/section label if identifiable, else null.
- category_leaf: the most specific product-category label stated or clearly
  implied, else null. Use catalog-style names (e.g. "Baby Floats",
  "DSLR Cameras"), not paths.
- price_max: number|null — only an explicit upper price bound.
- min_rating: number|null — only an explicit minimum rating.
- exclusions: {"item_ids": [...], "category_labels": [...]} — things the user
  asked NOT to see (empty lists when none).
- seed_item_id: product id string if the user references a specific item
  (e.g. "Domain::ASIN" style or bare ASIN), else null.
- attributes: object of inferred soft attributes {brand, material, ...} or null.
- language: "vi" | "en" | "mixed" | "unknown".

Rules: extract only what the text supports; do not invent categories, prices,
or items. If the request is too vague to fill any slot, still return kind and
nulls. JSON object only."""

PARAPHRASE_SYSTEM = """You rewrite e-commerce user requests. Output ONE JSON object
{"text": "..."} — the rewritten request only, no commentary.
Variant rules:
- en: faithful English translation, keep all specifics.
- vi_paraphrase: Vietnamese paraphrase, same meaning, different wording.
- code_mix: Vietnamese sentence mixing English product terms naturally.
- underspecified: Vietnamese, keep it a plausible request but REMOVE specifics
  (drop category names, prices, exclusions where present); do not add new ones.
Never name a specific product model/ASIN/title beyond what the original gives."""

LEAK_SYSTEM = """You check whether a product-request text leaks the identity of a
specific catalog item. Output ONE JSON object {"leak": true|false, "guess":
"item description or null"}. leak=true only if the text describes a unique
specific product (title/model/ASIN-level detail), not just a category."""


def provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        model=MODEL,
        timeout_seconds=180,
    )


def done_ids(path: Path, key: str = "request_id") -> set[str]:
    if not path.is_file():
        return set()
    ids = set()
    for line in open(path, encoding="utf-8"):
        if line.strip():
            try:
                ids.add(json.loads(line)[key])
            except Exception:
                pass
    return ids


def call(llm, system: str, user: str, *, json_mode: bool = True, max_tokens: int = 700,
         temperature: float = 0.0):
    msgs = [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]
    return llm.complete(msgs, temperature=temperature, max_tokens=max_tokens,
                        response_format_json=json_mode).text


def load_gold() -> list[dict]:
    return [json.loads(l) for l in open(GOLD, encoding="utf-8") if l.strip()]


def cmd_paraphrase(args) -> None:
    out = OUT / "paraphrases.jsonl"
    have = done_ids(out, "row_id")
    llm = provider()
    rows = []
    n_done = n_cost = 0
    for g in load_gold():
        for i, ptype in enumerate(PARAPHRASE_TYPES):
            row_id = f"{g['request_id']}|{ptype}"
            if row_id in have:
                continue
            if args.limit and n_done >= args.limit:
                break
            user = f"Original request:\n{g['text']}\n\nVariant: {ptype}"
            try:
                text = call(llm, PARAPHRASE_SYSTEM, user, max_tokens=400)
                payload = json.loads(text[text.index("{"):text.rindex("}") + 1])
                rows.append({"row_id": row_id, "request_id": g["request_id"],
                             "kind": g["kind"], "variant": ptype,
                             "text": payload.get("text", "")})
                n_done += 1
            except Exception as e:  # noqa: BLE001 — record and continue
                rows.append({"row_id": row_id, "request_id": g["request_id"],
                             "kind": g["kind"], "variant": ptype,
                             "text": "", "error": str(e)[:200]})
                n_done += 1
        if args.limit and n_done >= args.limit:
            break
        if rows:
            with open(out, "a", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            rows.clear()
            print(f"paraphrase: {n_done} calls", flush=True)
    if rows:
        with open(out, "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"paraphrase done -> {out}", flush=True)


def _shard(row_id: str, shard: int, nshards: int) -> bool:
    if nshards <= 1:
        return True
    return int(hashlib.md5(row_id.encode()).hexdigest(), 16) % nshards == shard


def cmd_leakcheck(args) -> None:
    src = OUT / "paraphrases.jsonl"
    out = OUT / "leakcheck.jsonl"
    have = done_ids(out, "row_id")
    llm = provider()
    pending = [json.loads(l) for l in open(src, encoding="utf-8")
               if l.strip() and json.loads(l).get("text")
               and json.loads(l)["row_id"] not in have
               and _shard(json.loads(l)["row_id"], args.shard, args.nshards)]
    print(f"leakcheck pending: {len(pending)}", flush=True)
    buf = []
    for i, r in enumerate(pending):
        try:
            text = call(llm, LEAK_SYSTEM, r["text"], max_tokens=200)
            payload = json.loads(text[text.index("{"):text.rindex("}") + 1])
            buf.append({"row_id": r["row_id"], "request_id": r["request_id"],
                        "variant": r["variant"], "leak": bool(payload.get("leak")),
                        "guess": payload.get("guess")})
        except Exception as e:  # noqa: BLE001
            buf.append({"row_id": r["row_id"], "request_id": r["request_id"],
                        "variant": r["variant"], "leak": None, "guess": None,
                        "error": str(e)[:200]})
        if len(buf) >= 50:
            with open(out, "a", encoding="utf-8") as f:
                for b in buf:
                    f.write(json.dumps(b, ensure_ascii=False) + "\n")
            buf.clear()
            print(f"leakcheck: {i + 1}/{len(pending)}", flush=True)
    if buf:
        with open(out, "a", encoding="utf-8") as f:
            for b in buf:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")
    print(f"leakcheck done -> {out}", flush=True)


def cmd_extract(args) -> None:
    suffix = f"_{args.tag}" if args.tag else ""
    out = OUT / f"extractor_outputs{suffix}.jsonl"
    have = done_ids(out, "row_id")
    llm = provider()

    inputs = []
    # originals: row_id = request_id, variant = "original"
    for g in load_gold():
        inputs.append({"row_id": g["request_id"], "request_id": g["request_id"],
                       "kind": g["kind"], "variant": "original", "text": g["text"]})
    # paraphrases (non-leaking only, if leakcheck exists)
    ppath = OUT / "paraphrases.jsonl"
    leaks = {}
    lpath = OUT / "leakcheck.jsonl"
    if lpath.is_file():
        leaks = {json.loads(l)["row_id"]: json.loads(l).get("leak")
                 for l in open(lpath, encoding="utf-8") if l.strip()}
    if ppath.is_file() and not getattr(args, "originals_only", False):
        for l in open(ppath, encoding="utf-8"):
            if not l.strip():
                continue
            r = json.loads(l)
            if not r.get("text") or r["row_id"] in have:
                continue
            if leaks.get(r["row_id"]) is True and not getattr(args, "include_leaked", False):
                continue  # leaked item identity -> excluded per protocol
            inputs.append({"row_id": r["row_id"], "request_id": r["request_id"],
                           "kind": r["kind"], "variant": r["variant"], "text": r["text"]})

    pending = [r for r in inputs
               if r["row_id"] not in have
               and _shard(r["row_id"], args.shard, args.nshards)]
    print(f"extract pending: {len(pending)} (shard {args.shard}/{args.nshards})", flush=True)
    buf = []
    for i, r in enumerate(pending):
        try:
            raw = call(llm, EXTRACT_SYSTEM, r["text"], max_tokens=800,
                       temperature=args.temp)
            start, end = raw.find("{"), raw.rfind("}")
            payload = json.loads(raw[start:end + 1]) if start >= 0 and end > start else None
            buf.append({"row_id": r["row_id"], "request_id": r["request_id"],
                        "kind": r["kind"], "variant": r["variant"],
                        "spec": payload, "struct_ok": payload is not None,
                        "raw": raw[:2000] if payload is None else None})
        except Exception as e:  # noqa: BLE001
            buf.append({"row_id": r["row_id"], "request_id": r["request_id"],
                        "kind": r["kind"], "variant": r["variant"],
                        "spec": None, "struct_ok": False, "error": str(e)[:200]})
        if len(buf) >= 50:
            with open(out, "a", encoding="utf-8") as f:
                for b in buf:
                    f.write(json.dumps(b, ensure_ascii=False) + "\n")
            buf.clear()
            print(f"extract: {i + 1}/{len(pending)}", flush=True)
    if buf:
        with open(out, "a", encoding="utf-8") as f:
            for b in buf:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")
    print(f"extract done -> {out}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("paraphrase"); p.add_argument("--limit", type=int, default=0)
    for name in ("leakcheck", "extract"):
        p = sub.add_parser(name)
        p.add_argument("--shard", type=int, default=0)
        p.add_argument("--nshards", type=int, default=1)
    sub.choices["extract"].add_argument("--originals-only", action="store_true")
    sub.choices["extract"].add_argument("--include-leaked", action="store_true")
    sub.choices["extract"].add_argument("--tag", default="")
    sub.choices["extract"].add_argument("--temp", type=float, default=0.0)
    args = ap.parse_args()
    {"paraphrase": cmd_paraphrase, "leakcheck": cmd_leakcheck,
     "extract": cmd_extract}[args.cmd](args)


if __name__ == "__main__":
    main()
