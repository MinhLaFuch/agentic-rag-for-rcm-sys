"""Pure scoring functions for the Phase-3 extractor benchmark (no I/O, no LLM).

Compares an extractor-predicted spec dict against a gold spec dict and returns
scalar metrics only (``summarize``-safe). Slot groups follow docs/BOTTLENECK.md §5:
kind / category / price / rating / exclusions / seed / language.

Category matching is LEVEL-AWARE via ``label_ancestors`` (label -> set of
ancestor labels reconstructed from item rowid sequences):
- exact: predicted == gold
- ancestor/descendant: related within taxonomy -> counts as 0.5 credit
- unrelated/absent -> 0
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

MATCH_EXACT = 1.0
MATCH_RELATED = 0.5
MATCH_NONE = 0.0


def category_match_level(
    pred: str | None,
    gold: str | None,
    label_ancestors: Mapping[str, frozenset[str]] | None = None,
) -> float:
    """0/0.5/1 credit for a predicted category label vs gold label."""
    if not pred or not gold:
        return MATCH_NONE
    if pred == gold:
        return MATCH_EXACT
    anc = label_ancestors or {}
    pred_anc = anc.get(pred, frozenset())
    gold_anc = anc.get(gold, frozenset())
    if gold in pred_anc or pred in gold_anc:
        return MATCH_RELATED
    # sibling under a shared ancestor also counts as related (same aisle)
    if pred_anc & gold_anc:
        return MATCH_RELATED
    return MATCH_NONE


def _slot_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    if tp + fp + fn == 0:
        return 0.0, 0.0, 0.0
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def _present(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) > 0
    return True


def _gold_slot(spec: Mapping[str, Any], name: str) -> Any:
    slot = spec.get(name)
    if isinstance(slot, dict):
        return slot.get("value")
    return slot


def score_category_slot(gold_spec: Mapping, pred: Mapping | None,
                        label_ancestors=None) -> dict[str, float]:
    """Category slot F1 at leaf level; also coarse-level credit."""
    gold_leaf = _gold_slot(gold_spec, "category_leaf")
    gold_coarse = _gold_slot(gold_spec, "category_coarse")
    p_leaf = (pred or {}).get("category_leaf")
    p_coarse = (pred or {}).get("category_coarse")

    tp = fp = fn = 0
    # leaf-level credit: best of (pred_leaf vs gold_leaf, pred_coarse vs gold_coarse,
    # pred_leaf vs gold_coarse) — extractor may answer at either granularity.
    credits = [
        category_match_level(p_leaf, gold_leaf, label_ancestors),
        category_match_level(p_coarse, gold_coarse, label_ancestors),
        category_match_level(p_leaf, gold_coarse, label_ancestors),
        # extractor may commit the specific label in the coarse slot
        category_match_level(p_coarse, gold_leaf, label_ancestors),
    ]
    credit = max(credits) if any(_present(g) for g in (gold_leaf, gold_coarse)) else 0.0
    if _present(gold_leaf) or _present(gold_coarse):
        if credit >= MATCH_EXACT:
            tp += 1
        elif credit >= MATCH_RELATED:
            tp += 1  # related counts as partial hit -> treat as tp for F1, see exact variant
            fp += 0
            fn += 0
        else:
            fp += 1
            fn += 1
    else:
        if _present(p_leaf) or _present(p_coarse):
            fp += 1
    p, r, f1 = _slot_f1(tp, fp, fn)
    return {
        "cat_precision": p, "cat_recall": r, "cat_f1": f1,
        "cat_exact": float(credit >= MATCH_EXACT and (_present(gold_leaf) or _present(gold_coarse))),
        "cat_any": float(credit > 0 and (_present(gold_leaf) or _present(gold_coarse))),
    }


def score_exclusion_slot(gold_spec: Mapping, pred: Mapping | None) -> dict[str, float]:
    g = gold_spec.get("exclusions") or {}
    p = (pred or {}).get("exclusions") or {}
    g_ids, p_ids = set(g.get("item_ids") or []), set(p.get("item_ids") or [])
    g_cats, p_cats = set(g.get("category_labels") or []), set(p.get("category_labels") or [])
    tp = len((g_ids & p_ids) | (g_cats & p_cats))
    fp = len((p_ids - g_ids) | (p_cats - g_cats))
    fn = len((g_ids - p_ids) | (g_cats - p_cats))
    # empty-vs-empty is a correct abstention, not a miss
    if not g_ids and not g_cats and not p_ids and not p_cats:
        tp = 1
    p_, r_, f1 = _slot_f1(tp, fp, fn)
    return {"excl_precision": p_, "excl_recall": r_, "excl_f1": f1}


def score_simple_slot(gold_spec: Mapping, pred: Mapping | None, name: str,
                      match=None) -> dict[str, float]:
    """Scalar slot (price_max, min_rating, seed_item_id, kind handled separately)."""
    g = _gold_slot(gold_spec, name) if name != "kind" else gold_spec.get("kind")
    p = pred.get(name) if pred else None
    if name in ("price_max", "min_rating") and p is not None:
        try:
            p = float(p)
        except (TypeError, ValueError):
            p = None
    eq = (match or (lambda a, b: a == b))(g, p) if _present(g) and _present(p) else None
    tp = fp = fn = 0
    if _present(g):
        if _present(p) and eq:
            tp = 1
        else:
            fn = 1
            if _present(p):
                fp = 1
    elif _present(p):
        fp = 1
    p_, r_, f1 = _slot_f1(tp, fp, fn)
    return {f"{name}_precision": p_, f"{name}_recall": r_, f"{name}_f1": f1}


def score_extraction(gold_spec: Mapping, gold_meta: Mapping,
                     pred: Mapping | None, *,
                     label_ancestors: Mapping[str, frozenset[str]] | None = None,
                     strict_valid: bool = False) -> dict[str, float]:
    """Full per-row score. ``gold_meta`` carries gold_coarse/gold_ancestor/
    variant language context from gold_specs.jsonl.

    ``strict_valid``: caller pre-validated pred against the Spec model —
    reported as ``struct_strict``; ``struct_ok`` is just "parsed JSON dict".
    """
    out: dict[str, float] = {
        "struct_ok": float(isinstance(pred, dict)),
        "struct_strict": float(bool(strict_valid)),
    }
    if not isinstance(pred, dict):
        pred = {}
    # kind accuracy (gold kind from gold_spec.kind == request kind)
    gkind = gold_spec.get("kind")
    pkind = pred.get("kind")
    out["kind_acc"] = float(pkind == gkind) if gkind else 0.0

    out.update(score_category_slot(gold_spec, pred, label_ancestors))
    out.update(score_exclusion_slot(gold_spec, pred))
    out.update(score_simple_slot(gold_spec, pred, "price_max"))
    out.update(score_simple_slot(gold_spec, pred, "min_rating"))
    out.update(score_simple_slot(gold_spec, pred, "seed_item_id"))

    # language: gold = variant-derived (original/vi_* -> vi, en -> en,
    # code_mix -> mixed, underspecified -> vi)
    variant = gold_meta.get("variant", "original")
    gold_lang = {"en": "en", "code_mix": "mixed"}.get(variant, "vi")
    pred_lang = pred.get("language")
    out["language_acc"] = float(pred_lang == gold_lang)

    # uncategorized_ok: gold always True in v1 -> measure pred agreement only
    out["uncategorized_ok_agree"] = float(
        pred.get("uncategorized_ok", True) is True
    )
    return out
