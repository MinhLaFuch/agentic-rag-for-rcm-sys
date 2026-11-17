"""Bounded keyset reads in canonical item-ID order, without catalog-wide text loading."""

from .format_catalog_text import format_catalog_text


def read_catalog_text_chunk(conn, after: str | None, limit: int):
    if limit <= 0:
        raise ValueError("chunk limit must be positive")
    where, params = ("", [limit]) if after is None else ("WHERE item_id > ?", [after, limit])
    selected = conn.execute(
        f"SELECT item_id, title, store, main_category FROM items {where} ORDER BY item_id LIMIT ?", params
    ).fetchall()
    categories = {row[0]: [] for row in selected}
    ids = list(categories)
    for start in range(0, len(ids), 256):
        group = ids[start:start + 256]
        marks = ','.join('?' for _ in group)
        for item_id, category in conn.execute(
            f"SELECT item_id, category FROM item_categories WHERE item_id IN ({marks}) ORDER BY item_id, category", group
        ):
            categories[item_id].append(category)
    return [(item_id, format_catalog_text(title, store, main, categories[item_id]))
            for item_id, title, store, main in selected]
