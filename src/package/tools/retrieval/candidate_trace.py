"""Collect target membership for offline evaluation without changing tool results."""

from contextlib import contextmanager
from contextvars import ContextVar
from ..base import ToolInputError


_active = ContextVar("candidate_trace", default=None)


@contextmanager
def trace_candidates(targets):
    records = {}
    token = _active.set((tuple(dict.fromkeys(targets)), records))
    try:
        yield records
    finally:
        _active.reset(token)


def record_generation(result, scope, *, item_ids=(), query=None):
    active = _active.get()
    if active is None or not active[0]:
        return result
    targets, records = active
    hits = set(targets).intersection(item_ids)
    hits.update(row["item_id"] for row in result["candidates"] if row["item_id"] in targets)
    membership = dict.fromkeys(targets, False)
    if query is not None:
        corpus, sql, params = query
        for target in targets:
            if target in hits:
                continue
            try:
                rows, _ = corpus.select(sql, [*params, target], max_rows=1)
                membership[target] = bool(rows)
            except ToolInputError:
                membership[target] = None
    membership.update(dict.fromkeys(hits, True))
    # Retain the result object so its id cannot be reused during reflection.
    records[id(result)] = (result, {
        "scope": scope,
        "targets": membership,
    })
    return result


def attach_candidate_trace(steps, records):
    for step in steps:
        entry = records.get(id(step.get("data")))
        if entry is not None:
            step["candidate_generation"] = entry[1]
