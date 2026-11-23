"""Policy-visible title lookup without category joins or catalog-wide grouping."""


def catalog_title_lookup(corpus, *, batch_size=64):
    """Return a cached namespaced-ID lookup compatible with history query metadata.

    Missing/hidden IDs are cached as misses; source TEMP policy view and normal
    SQL timeout/authorizer remain active. Never read main.items directly.
    """
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError('Title lookup batch size must be positive')
    cache = {}

    def get(item_ids):
        requested = list(dict.fromkeys(item_ids))
        missing = [item for item in requested if item not in cache]
        for start in range(0, len(missing), batch_size):
            chunk = missing[start:start + batch_size]
            marks = ','.join('?' for _ in chunk)
            rows, truncated = corpus.select(
                f'SELECT item_id, title FROM items WHERE item_id IN ({marks})', chunk,
                max_rows=len(chunk))
            if truncated:
                raise ValueError('Title lookup unexpectedly truncated')
            cache.update((item, None) for item in chunk)
            for row in rows:
                cache[row['item_id']] = (row.get('title') or '', '')
        return {item: cache[item] for item in requested if cache.get(item) is not None}

    return get
