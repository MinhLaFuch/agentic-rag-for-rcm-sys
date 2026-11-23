"""Post-hoc Jev judge pass over agent-eval trajectories.

For every trajectory whose ``answer_status == "ok"`` this asks Jev (TypeSafe AI
/ OpenRouter System One) to score the answer's faithfulness (claim-level support)
and communication quality, using the recommended items' corpus metadata as the
evidence — the real-answer counterpart of the component grounding benchmark,
which runs on a synthetic dataset.

Rows carry request context (request_id/agent/kind/segment/oracle) plus the
judge result fields verbatim (evaluation_state, counts, communication, usage).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from package.corpus import ItemCorpus
from package.evaluation.product_reply.evaluate_product_reply_with_jev import (
    evaluate_product_reply_with_jev,
)

_ITEM_FIELDS = (
    "item_id, domain, title, store, price, average_rating, rating_number, main_category"
)


def _items_for(corpus: ItemCorpus, item_ids: list[str]) -> list[dict[str, Any]]:
    """Corpus metadata rows for the recommended item_ids, in request order."""
    if not item_ids:
        return []
    placeholders = ",".join("?" for _ in item_ids)
    rows, _ = corpus.select(
        f"SELECT {_ITEM_FIELDS} FROM items WHERE item_id IN ({placeholders})",
        tuple(item_ids),
        max_rows=len(item_ids),
    )
    by_id = {r["item_id"]: r for r in rows}
    return [by_id[i] for i in item_ids if i in by_id]


def evaluate_trajectories_with_jev(
    trajectories: list[dict[str, Any]],
    requests_by_id: Mapping[str, Any],
    corpus: ItemCorpus,
    *,
    max_requests: int | None = None,
) -> list[dict[str, Any]]:
    """Judge every answered trajectory; returns one row per judged request.

    Eligibility: ``answer_status == "ok"``, non-empty ``answer``, non-empty
    ``recommended``. ``max_requests`` caps the count deterministically in
    trajectory order (cost control). Requests missing from ``requests_by_id``
    are skipped — a trajectory without its request cannot be honestly judged.
    """
    rows: list[dict[str, Any]] = []
    for traj in trajectories:
        if max_requests is not None and len(rows) >= max_requests:
            break
        if traj.get("answer_status") != "ok" or not traj.get("answer"):
            continue
        recommended = traj.get("recommended") or []
        if not recommended:
            continue
        request = requests_by_id.get(traj.get("request_id"))
        if request is None:
            continue
        items = _items_for(corpus, list(dict.fromkeys(recommended)))
        if not items:
            continue
        result = evaluate_product_reply_with_jev(request.text, items, traj["answer"])
        rows.append(
            {
                "request_id": traj["request_id"],
                "agent": traj.get("agent"),
                "kind": getattr(request, "kind", None),
                "segment": getattr(request, "segment", None),
                "oracle": getattr(request, "oracle", None),
                **result,
            }
        )
    return rows
