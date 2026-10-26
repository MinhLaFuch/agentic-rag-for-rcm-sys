"""Column definitions for Layer 1: Recommendation Outcome."""

COLUMNS = (
    "n_recommended",
    "precision@k",
    "recall@k",
    "hit_rate@k",
    "ndcg@k",
    "mrr@k",
    "map@k",
    "seen_item_rate",
    "seed_in_result",
    "distinct_domains",
    "distinct_main_categories",
)
