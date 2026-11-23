"""Enumerate policy-visible catalog IDs in bounded indexed ranges."""


def eligible_catalog_ids(corpus, catalog_ids, *, page_size=2048):
    """Use sorted full-artifact IDs as range boundaries, retaining TEMP policy views.

    Range bounds avoid a catalog-wide fetch and avoid a sparse last-page keyset
    query scanning an arbitrarily large hidden tail within one SQL time budget.
    Only the public corpus.select API is used; authorizers/timeouts stay active.
    """
    if type(page_size) is not int or page_size <= 0:
        raise ValueError('page_size must be a positive integer')
    eligible = set()
    previous = None
    for start in range(0, len(catalog_ids), page_size):
        page = [str(item) for item in catalog_ids[start:start + page_size]]
        if (not page or any(a >= b for a, b in zip(page, page[1:]))
                or (previous is not None and page[0] <= previous)):
            raise ValueError('Catalog IDs must be strictly sorted and unique')
        rows, truncated = corpus.select(
            'SELECT item_id FROM items WHERE item_id >= ? AND item_id <= ? ORDER BY item_id',
            [page[0], page[-1]], max_rows=len(page))
        allowed = set(page)
        if truncated or any(row['item_id'] not in allowed for row in rows):
            raise ValueError('Policy-visible corpus differs from artifact ID ranges')
        eligible.update(row['item_id'] for row in rows)
        previous = page[-1]
        if start == 0 or start // page_size % 100 == 0 or start + page_size >= len(catalog_ids):
            print(f'[eligibility] checked={min(start + page_size, len(catalog_ids)):,}/{len(catalog_ids):,} visible={len(eligible):,}', flush=True)
    return eligible
