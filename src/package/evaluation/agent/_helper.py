"""Corpus lookups used both to build constrained requests and to check the agent's answers."""

from __future__ import annotations

from typing import Sequence

from ...tools.corpus import ItemCorpus


def _price_of(corpus: ItemCorpus, item_id: str) -> float | None:
    rows, _ = corpus.select("SELECT price FROM items WHERE item_id = ?", (item_id,), max_rows=1)
    return rows[0]["price"] if rows else None


def _deepest_category(corpus: ItemCorpus, item_id: str) -> str | None:
    """Last category of the item: `categories` is a taxonomy path (root -> leaf), rows are inserted in that order."""
    rows, _ = corpus.select(
        "SELECT category FROM item_categories WHERE item_id = ? ORDER BY rowid DESC LIMIT 1", (item_id,), max_rows=1
    )
    return rows[0]["category"] if rows else None


def items_satisfying(
    corpus: ItemCorpus, item_ids: Sequence[str], price_max: float | None, category: str | None
) -> set[str]:
    """Items among `item_ids` with a KNOWN price <= price_max (if given) and the category (if given)."""
    ids = list(dict.fromkeys(item_ids))
    if not ids:
        return set()
    sql = f"SELECT items.item_id FROM items WHERE items.item_id IN ({','.join('?' * len(ids))})"
    params: list = list(ids)
    if price_max is not None:
        sql += " AND items.price IS NOT NULL AND items.price <= ?"
        params.append(float(price_max))
    if category is not None:
        sql += " AND EXISTS (SELECT 1 FROM item_categories c WHERE c.item_id = items.item_id AND c.category = ?)"
        params.append(category)
    rows, _ = corpus.select(sql, params, max_rows=len(ids))
    return {r["item_id"] for r in rows}


def items_without_price(corpus: ItemCorpus, item_ids: Sequence[str]) -> set[str]:
    ids = list(dict.fromkeys(item_ids))
    if not ids:
        return set()
    sql = f"SELECT items.item_id FROM items WHERE items.item_id IN ({','.join('?' * len(ids))}) AND items.price IS NULL"
    rows, _ = corpus.select(sql, ids, max_rows=len(ids))
    return {r["item_id"] for r in rows}
