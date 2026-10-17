"""Build the evaluation requests from held-out data (no real query log exists offline, so they are simulated)."""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from ...tools.corpus import ItemCorpus
from ._dataclass import AgentRequest
from ._helper import _deepest_category, _price_of, items_satisfying
from ._schema import KIND_SEGMENTS, ORACLE_KINDS, TEMPLATES


def build_requests(
    *,
    seg_of: Mapping[int, str],  # user_idx -> cold | sparse | warm, for users who have held-out items
    target_by_user: Mapping[int, set[int]],  # user_idx -> held-out item_idx
    last_item_of: Mapping[int, int],  # user_idx -> most recent fit item_idx
    id2user: Mapping[int, str],
    id2item: Mapping[int, str],
    item2id: Mapping[str, int],
    corpus: ItemCorpus,
    per_segment: int,  # max requests per (kind, segment)
    n_ambiguous: int,
    language: str,
    k: int,  # number of recommendations asked for in the text
    price_slack: float,  # budget = held-out price * price_slack, rounded UP to a multiple of price_round_to
    price_round_to: float,
    rng: np.random.Generator,
) -> list[AgentRequest]:
    if language not in TEMPLATES:
        raise ValueError(f"language must be one of {sorted(TEMPLATES)}, got {language!r}")
    templates = TEMPLATES[language]
    requests: list[AgentRequest] = []

    def users_in(segment: str) -> list[int]:
        pool = sorted(u for u, s in seg_of.items() if s == segment)
        return [int(u) for u in rng.permutation(pool)]

    def add(kind: str, segment: str, **fields) -> None:
        index = sum(1 for r in requests if r.kind == kind and r.segment == segment)
        requests.append(
            AgentRequest(
                request_id=f"{kind}-{segment}-{index}", kind=kind, segment=segment, oracle=kind in ORACLE_KINDS, **fields
            )
        )

    for segment in KIND_SEGMENTS["similar"]:
        for u in users_in(segment):
            if sum(1 for r in requests if r.kind == "similar" and r.segment == segment) >= per_segment:
                break
            if u not in last_item_of:
                continue
            seed = id2item[last_item_of[u]]
            add("similar", segment, user_id=id2user[u], user_idx=u, seed_item_id=seed,
                targets=sorted(target_by_user[u]),
                text=templates["similar"].format(user_id=id2user[u], item_id=seed, k=k))

    for segment in KIND_SEGMENTS["personalized"]:
        for u in users_in(segment):
            if sum(1 for r in requests if r.kind == "personalized" and r.segment == segment) >= per_segment:
                break
            add("personalized", segment, user_id=id2user[u], user_idx=u, targets=sorted(target_by_user[u]),
                text=templates["personalized"].format(user_id=id2user[u], k=k))

    for segment in KIND_SEGMENTS["constrained"]:
        for u in users_in(segment):
            if sum(1 for r in requests if r.kind == "constrained" and r.segment == segment) >= per_segment:
                break
            held_out = [id2item[i] for i in sorted(target_by_user[u])]
            picked = next(  # first held-out item with a known price and a category
                ((p, c) for item in held_out if (p := _price_of(corpus, item)) is not None
                 and (c := _deepest_category(corpus, item))),
                None,
            )
            if picked is None:
                continue
            price, category = picked
            price_max = math.ceil(price * price_slack / price_round_to) * price_round_to
            relevant = items_satisfying(corpus, held_out, price_max, category)  # held-out items that meet BOTH constraints
            add("constrained", segment, user_id=id2user[u], user_idx=u, price_max=float(price_max), category=category,
                targets=sorted(item2id[i] for i in relevant),
                text=templates["constrained"].format(user_id=id2user[u], k=k, category=category, price_max=f"{price_max:g}"))

    for segment in KIND_SEGMENTS["cold_text"]:
        for u in users_in(segment):
            if sum(1 for r in requests if r.kind == "cold_text" and r.segment == segment) >= per_segment:
                break
            held_out = [id2item[i] for i in sorted(target_by_user[u])]
            category = next((c for item in held_out if (c := _deepest_category(corpus, item))), None)
            if category is None:
                continue
            relevant = items_satisfying(corpus, held_out, None, category)
            add("cold_text", segment, user_id=id2user[u], user_idx=u, category=category,
                targets=sorted(item2id[i] for i in relevant),
                text=templates["cold_text"].format(user_id=id2user[u], k=k, category=category))

    phrasings = templates["ambiguous"]
    for i in range(n_ambiguous):
        add("ambiguous", "none", text=phrasings[i % len(phrasings)])

    return requests
