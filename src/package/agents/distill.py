"""Query distillation: extract a structured Spec from raw request text.

Runs once per request (pre-planner injection, flag ``agent_eval.distill_spec``).
The extractor is a single LLM call with a strict JSON contract; output is
validated against ``package.evaluation.spec.Spec`` and category labels are
normalized against the corpus (exact / case-insensitive canonical form only —
fuzzy suggestions are left for FilterTool's own validation to report).
"""

from __future__ import annotations

import difflib
import json
from typing import Any

from ..api import LLMMessage, LLMProvider, LLMProviderError
from ..evaluation.spec import Spec

DISTILL_SYSTEM = """You are a query distiller for an e-commerce recommendation agent.
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

_SPEC_FIELDS = (
    "kind", "category_coarse", "category_leaf", "price_max", "min_rating",
    "exclusions", "seed_item_id", "attributes", "language", "uncategorized_ok",
)


def _adapt_for_spec(pred: dict[str, Any]) -> dict[str, Any]:
    """Extractor emits flat category strings; Spec wants CategorySlot objects."""
    out = {k: pred[k] for k in _SPEC_FIELDS if k in pred}
    for k in ("category_leaf", "category_coarse"):
        v = pred.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = {"value": v}
        elif isinstance(v, dict):
            out[k] = v
    return out


def _normalize_labels(spec: dict[str, Any], corpus: Any) -> dict[str, Any]:
    """Canonicalize category labels via corpus (exact or case-only match).
    Unresolvable labels are kept verbatim — FilterTool reports suggestions."""
    for slot in ("category_leaf", "category_coarse"):
        s = spec.get(slot)
        if isinstance(s, dict) and isinstance(s.get("value"), str):
            canon = corpus.normalize_category_case(s["value"])
            if canon:
                s["value"] = canon
    ex = spec.get("exclusions")
    if isinstance(ex, dict):
        labels = ex.get("category_labels") or []
        ex["category_labels"] = [
            corpus.normalize_category_case(c) or c for c in labels
        ]
    return spec


_CATEGORY_LEXICON_CACHE: dict[int, list[str]] = {}


def _category_lexicon(corpus: Any) -> list[str]:
    """Distinct category labels, cached per corpus object (one scan)."""
    key = id(corpus)
    if key not in _CATEGORY_LEXICON_CACHE:
        try:
            _CATEGORY_LEXICON_CACHE[key] = corpus.categories()
        except Exception:  # noqa: BLE001 — lexicon is advisory only
            _CATEGORY_LEXICON_CACHE[key] = []
    return _CATEGORY_LEXICON_CACHE[key]


def _flag_unverified_categories(out: dict[str, Any], corpus: Any) -> dict[str, Any]:
    """Mark category labels that don't exist in the catalog.

    The extractor has no catalog access, so it happily emits plausible-looking
        but fake labels (e.g. "NonExistentCategory999") for unanswerable
        requests. ``category_unverified`` lists labels that fail both exact /
        case-normalized match and a strict fuzzy match (cutoff 0.8) — the
        planner prompt tells the agent to clarify rather than force retrieval.
    """
    labels: list[str] = []
    for slot in ("category_leaf", "category_coarse"):
        v = out.get(slot)
        if isinstance(v, str) and v.strip():
            labels.append(v)
    ex = out.get("exclusions")
    if isinstance(ex, dict):
        labels.extend(c for c in (ex.get("category_labels") or [])
                      if isinstance(c, str) and c.strip())
    if not labels:
        return out
    lexicon = _category_lexicon(corpus)
    bad = set()
    for label in labels:
        if corpus.normalize_category_case(label) is not None:
            continue
        if lexicon and difflib.get_close_matches(label, lexicon, n=1, cutoff=0.8):
            continue
        bad.add(label)
    if bad:
        out["category_unverified"] = sorted(bad)
    return out


def extract_spec(
    llm: LLMProvider,
    text: str,
    *,
    corpus: Any = None,
    temperature: float = 0.0,
    max_tokens: int = 800,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """One extractor call. Returns (spec_dict | None, usage_dict).

    spec_dict is the validated Spec dump (compact: only non-null fields plus
    kind), or None when the reply is unparseable / fails Spec validation.
    usage_dict carries token/latency accounting for cost attribution.
    """
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "latency_seconds": 0.0,
             "attempts": 1, "error": None}
    try:
        resp = llm.complete(
            [LLMMessage(role="system", content=DISTILL_SYSTEM),
             LLMMessage(role="user", content=text)],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format_json=True,
        )
    except LLMProviderError as exc:
        usage["error"] = f"{type(exc).__name__}: {exc}"
        return None, usage
    usage["prompt_tokens"] = resp.prompt_tokens or 0
    usage["completion_tokens"] = resp.completion_tokens or 0
    usage["latency_seconds"] = resp.latency_seconds or 0.0

    raw = resp.text
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        usage["error"] = "no JSON object in reply"
        return None, usage
    try:
        pred = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        usage["error"] = f"JSONDecodeError: {exc}"
        return None, usage
    if not isinstance(pred, dict):
        usage["error"] = "payload is not an object"
        return None, usage
    try:
        spec = Spec(**_adapt_for_spec(pred))
    except Exception as exc:  # noqa: BLE001 — pydantic ValidationError etc.
        usage["error"] = f"Spec validation failed: {exc}"[:300]
        return None, usage

    out = spec.model_dump(exclude_none=True)
    if corpus is not None:
        out = _normalize_labels(out, corpus)
    # flatten CategorySlot objects to plain label strings for a compact prompt block
    for slot in ("category_leaf", "category_coarse"):
        s = out.get(slot)
        if isinstance(s, dict):
            out[slot] = s.get("value")
            if out[slot] is None:
                del out[slot]
    out = {k: v for k, v in out.items() if v not in (None, {}, [])}
    if corpus is not None:
        out = _flag_unverified_categories(out, corpus)
    return out, usage


def make_spec_extractor(llm: LLMProvider, corpus: Any = None):
    """Callable ``(text) -> (spec|None, usage)`` bound for PlanExecutor."""
    def _extract(text: str):
        return extract_spec(llm, text, corpus=corpus)
    return _extract
