"""Independent oracle for item-item KNN expectations in executor/integration datasets.

Reimplements the fixture math WITHOUT importing the code under test
(ItemKNNRecommender / BaselineScorer / SimilarTool / RankTool):

  user_items  = binary csr (user_idx x item_idx) from create_test_interactions
  cooccur     = X.T @ X, diagonal removed
  similarity  = cosine-normalized co-occurrence, top-10 neighbours per row
                (mirrors BaselineItemKNNRecommender.fit + _keep_top_neighbors)
  similar(vg_a, top_k=5): row of similarity for the seed, score desc then
                item index asc, seed excluded (SimilarTool exclude_input)
  rank(user, candidates): BaselineScorer.score = popularity_weight*pop_norm
                + (user_row @ similarity); exclude_seen drops the user's
                history items; order = score desc, stable (input order ties)

Run:  PYTHONPATH=. python scripts/eda_diagnostic/oracle_fixture_knn.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse

from package.evaluation.component.benchmarks import (
    create_test_interactions,
    create_test_mappings,
)

NEIGHBORS = 10          # ItemKNNRecommender(10) in the benchmarks
POPULARITY_WEIGHT = 1e-6  # BaselineScorer default


def build_similarity(interactions: pd.DataFrame, num_items: int) -> sparse.csr_matrix:
    users = interactions["user_idx"].to_numpy(dtype=np.int64)
    items = interactions["item_idx"].to_numpy(dtype=np.int64)
    n_users = int(users.max()) + 1
    X = sparse.csr_matrix(
        (np.ones(len(interactions), dtype=np.float32), (users, items)),
        shape=(n_users, num_items),
    )
    X.data[:] = 1.0
    X.eliminate_zeros()

    co = (X.T @ X).tocsr().astype(np.float64)
    co.setdiag(0)
    co.eliminate_zeros()
    norms = np.sqrt(np.asarray(X.getnnz(axis=0), dtype=np.float64))
    rows = np.repeat(np.arange(co.shape[0]), np.diff(co.indptr))
    co.data /= norms[rows] * norms[co.indices]

    # top-NEIGHBORS per row (argpartition like _keep_top_neighbors)
    out_r, out_c, out_v = [], [], []
    for r in range(co.shape[0]):
        s, e = co.indptr[r], co.indptr[r + 1]
        if e <= s:
            continue
        vals, cols = co.data[s:e], co.indices[s:e]
        take = min(NEIGHBORS, len(vals))
        keep = np.argpartition(vals, -take)[-take:]
        out_r.append(np.full(take, r)); out_c.append(cols[keep]); out_v.append(vals[keep])
    sim = sparse.csr_matrix(
        (np.concatenate(out_v), (np.concatenate(out_r), np.concatenate(out_c))),
        shape=co.shape,
    )
    return X.tocsr(), sim


def similar_ids(sim: sparse.csr_matrix, seed_idx: int, top_k: int, exclude: set[int]) -> list[int]:
    row = sim.getrow(seed_idx).tocoo()
    order = np.lexsort((row.col, -row.data))  # score desc, col idx asc
    cols = row.col[order]
    return [int(c) for c in cols if int(c) not in exclude][:top_k]


def rank_ids(X, sim, popularity, user_idx: int, cand_idxs: list[int], exclude_seen: bool) -> list[int]:
    peak = popularity.max() if len(popularity) else 0.0
    pop_norm = popularity / peak if peak > 0 else popularity
    scores = pop_norm[np.asarray(cand_idxs)] * POPULARITY_WEIGHT
    known = 0 <= user_idx < X.shape[0] and X.getrow(user_idx).nnz > 0
    if known:
        cf = (X.getrow(user_idx) @ sim).tocsr()
        scores = scores + np.asarray(cf[:, cand_idxs].toarray()).ravel()
    keep = list(range(len(cand_idxs)))
    excluded = []
    if exclude_seen and known:
        seen = set(X.getrow(user_idx).indices.tolist())
        keep = [i for i in keep if cand_idxs[i] not in seen]
        excluded = [cand_idxs[i] for i in range(len(cand_idxs)) if cand_idxs[i] in seen]
    order = sorted(keep, key=lambda i: -scores[i])  # stable: ties keep input order
    return [cand_idxs[i] for i in order], excluded


def main() -> None:
    interactions = create_test_interactions()
    user2id, item2id, id2item = create_test_mappings(interactions)
    num_items = int(interactions["item_idx"].max()) + 1
    X, sim = build_similarity(interactions, num_items)
    popularity = np.bincount(
        interactions["item_idx"].to_numpy(dtype=np.int64), minlength=num_items
    ).astype(np.float64)

    # --- exec_021 / int_013 chain: SimilarTool(vg_a, top_k=5) -> RankTool(u_long)
    seed = item2id["Video_Games::vg_a"]
    cands = similar_ids(sim, seed, top_k=5, exclude={seed})
    print("similar(vg_a,5) item_idx:", cands)
    print("similar(vg_a,5) item_ids:", [id2item[i] for i in cands])

    u_long = user2id["u_long"]
    ranked, excluded = rank_ids(X, sim, popularity, u_long, cands, exclude_seen=True)
    print("rank(u_long) ranked_idx:", ranked)
    print("rank(u_long) ranked_ids:", [id2item[i] for i in ranked])
    print("rank(u_long) excluded_seen_idx:", excluded)

    # cold user variant for contrast (u_empty -> popularity only, no exclusions)
    u_empty = user2id["u_empty"]
    ranked_cold, _ = rank_ids(X, sim, popularity, u_empty, cands, exclude_seen=True)
    print("rank(u_empty) ranked_ids:", [id2item[i] for i in ranked_cold])

    # u_short: partial overlap with candidates (vg_b seen, rest not)
    u_short = user2id["u_short"]
    ranked_short, excl_short = rank_ids(X, sim, popularity, u_short, cands, exclude_seen=True)
    print("rank(u_short) ranked_ids:", [id2item[i] for i in ranked_short])
    print("rank(u_short) excluded_seen_ids:", [id2item[i] for i in excl_short])

    # scores detail for audit
    peak = popularity.max()
    pop_norm = popularity / peak
    cf = (X.getrow(u_long) @ sim).tocsr()
    for i in cands:
        s = pop_norm[i] * POPULARITY_WEIGHT + float(cf[:, i].toarray().ravel()[0])
        print(f"  cand {id2item[i]} idx={i} score={s:.6f} seen={i in set(X.getrow(u_long).indices.tolist())}")


if __name__ == "__main__":
    main()
