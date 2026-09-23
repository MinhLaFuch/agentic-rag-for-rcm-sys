from dataclasses import dataclass, field

@dataclass
class InteractionStats:
    num_users: int
    num_items: int
    num_interactions: int
    sparsity: float  # 1 - num_interactions / (num_users * num_items)
    avg_interactions_per_user: float
    median_interactions_per_user: float
    p90_interactions_per_user: float
    timestamp_min: int
    timestamp_max: int