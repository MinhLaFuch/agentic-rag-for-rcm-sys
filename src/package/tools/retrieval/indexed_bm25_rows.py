"""Exact filtered BM25 Top-K using FTS5 rank streaming and boundary-tie refill."""

from ..base import ToolInputError


def _joined_filtered_rows(corpus, match, columns, where, params, limit, max_scan):
    """Run filtering and deterministic ordering inside SQLite.

    The previous implementation fetched an unfiltered FTS prefix and then
    looked up metadata in Python.  On a broad query, most of that prefix could
    be rejected by the metadata policy, causing repeated scans and SQL timeouts.
    Joining ``items`` before LIMIT lets SQLite apply the same policy/filter
    predicates while the FTS index is still driving the query.
    """
    take = min(max_scan, max(256, limit * 2))
    sql = (
        f"SELECT items.rowid AS fts_rowid, rank AS relevance, {columns} "
        "FROM items_fts JOIN items ON items.rowid = items_fts.rowid "
        f"WHERE items_fts MATCH ? AND {where} "
        "ORDER BY rank ASC, items.rating_number DESC, items.item_id ASC "
        "LIMIT ?"
    )
    rows, truncated = corpus.select(sql, [match, *params, take], max_rows=take)
    if not rows:
        return [], False
    for row in rows:
        row['score'] = -float(row.pop('relevance'))
        row.pop('fts_rowid', None)
    # ``corpus.select`` reports whether LIMIT was reached; the result order is
    # already total (rank, rating, item_id), so no boundary refill is needed.
    return rows[:limit], bool(truncated)


def indexed_bm25_rows(corpus, match, columns, where, params, limit, *, max_scan=131072):
    """Return exact filtered BM25 Top-K without materialising broad prefixes.

    The joined path is used for the real ItemCorpus.  A small compatibility
    fallback retains the old two-query protocol for minimal test doubles that
    only implement an FTS prefix and metadata lookup; production code never
    relies on that fallback.
    """
    if type(limit) is not int or limit <= 0 or type(max_scan) is not int or max_scan < limit:
        raise ValueError('Invalid BM25 indexed limits')

    if hasattr(corpus, '_conn'):
        rows, truncated = _joined_filtered_rows(corpus, match, columns, where, params, limit, max_scan)
        if rows or not truncated:
            return rows, truncated

    # Compatibility path for narrow test doubles / legacy corpus adapters.
    take = min(max_scan, max(256, limit * 2))
    seen_rows, candidates = set(), {}
    while True:
        raw, more = corpus.select(
            'SELECT rowid AS fts_rowid, rank AS relevance FROM items_fts '
            'WHERE items_fts MATCH ? ORDER BY rank LIMIT ?',
            [match, take + 1], max_rows=take)
        fresh = [r for r in raw if r['fts_rowid'] not in seen_rows]
        for start in range(0, len(fresh), 256):
            batch = fresh[start:start + 256]
            scores = {r['fts_rowid']: -float(r['relevance']) for r in batch}
            marks = ','.join('?' for _ in batch)
            metadata_rows, metadata_truncated = corpus.select(
                f'SELECT items.rowid AS fts_rowid, {columns} FROM items '
                f'WHERE items.rowid IN ({marks}) AND {where}',
                [*scores, *params], max_rows=len(batch))
            if metadata_truncated:
                raise ToolInputError('BM25 metadata lookup unexpectedly truncated')
            for row in metadata_rows:
                row['score'] = scores[row.pop('fts_rowid')]
                candidates[row['item_id']] = row
            seen_rows.update(scores)
        ordered = sorted(candidates.values(), key=lambda r: (
            -r['score'], -(r.get('rating_number') if r.get('rating_number') is not None else float('-inf')),
            r['item_id']))
        proven = len(ordered) > limit and raw and ordered[limit]['score'] > -float(raw[-1]['relevance'])
        if not more or proven:
            return ordered[:limit], len(ordered) > limit or more
        if take >= max_scan:
            raise ToolInputError('BM25 exact Top-K scan cap reached; refine query or review explicit scan budget')
        take = min(take * 2, max_scan)
