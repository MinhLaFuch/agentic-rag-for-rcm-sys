"""Fixed-pool replay of recorded recency signals, with no model or labels."""


def recent_priority_order(pool,current_top,latest_top,latest_cf,policy):
    allowed=set(pool)
    if len(pool)!=len(allowed) or len(current_top)!=len(set(current_top)) or not set(current_top)<=allowed:
        raise ValueError("invalid pool or saved ranking")
    if len(current_top)!=min(10,len(pool)):
        raise ValueError("saved ranking is incomplete at 10; cannot infer missing scores")
    if policy=="latest_top3_guard":
        prefix=[i for i in latest_top[:3] if i in allowed]
    elif policy=="latest_cf_first":
        prefix=[i for i in latest_cf if i in allowed]
    else:
        raise ValueError("unknown recent-priority policy")
    return list(dict.fromkeys(prefix+current_top+pool))
