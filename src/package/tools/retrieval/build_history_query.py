"""History-only query representation shared by offline evaluation and runtime."""

import math

import unicodedata


def build_history_query(history, *, mode="latest_title", max_items=3, decay=.5, cutoff=None,
                        normalization="raw"):
    """Accept fit events with item_id/title/timestamp, never a target collection.

    Stable timestamp-descending/item-ID-ascending order, latest event per item.
    Recency weights apply to dense component vectors; BM25 receives the explicitly
    recorded concatenation (FTS OR matching cannot express vector weights).
    """
    if mode not in ("latest_title", "multi_history", "recency_weighted"):
        raise ValueError("Unknown history query mode")
    if (max_items <= 0 or not math.isfinite(decay) or not 0 < decay <= 1
            or (cutoff is not None and (isinstance(cutoff, bool) or not isinstance(cutoff, (int, float))
                                        or not math.isfinite(cutoff)))):
        raise ValueError("Invalid history query settings")
    if normalization not in ("raw", "ascii_fold"):
        raise ValueError("Unknown query normalization")
    events = sorted((e for e in history if cutoff is None or int(e['timestamp']) < cutoff),
                    key=lambda e: (-int(e['timestamp']), str(e['item_id'])))
    components, seen = [], set()
    for event in events:
        item = str(event['item_id'])
        if item in seen:
            continue
        seen.add(item)
        title = str(event.get('title') or '').strip()
        if normalization == 'ascii_fold':
            title = ''.join(c if ord(c) < 128 else ' ' for c in unicodedata.normalize('NFKD', title)
                            if not unicodedata.combining(c))
            title = ' '.join(title.split())
        # latest_title preserves an empty latest title; never falls through to older targets/history.
        components.append({'item_id': item, 'timestamp': int(event['timestamp']), 'text': title})
        if len(components) >= (1 if mode == 'latest_title' else max_items):
            break
    for rank, component in enumerate(components):
        component['weight'] = decay**rank if mode == 'recency_weighted' else 1.
    return {'mode': mode, 'components': components,
            'text': ' '.join(c['text'] for c in components if c['text']),
            'normalization': normalization, 'cutoff_exclusive': cutoff,
            'target_used': False, 'dense_aggregation': 'normalized_weighted_mean',
            'lexical_aggregation': 'newest_first_concatenation'}
