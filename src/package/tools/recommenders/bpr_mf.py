from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .base import Recommender


class BPRMFRecommender(Recommender):
    name = "bpr_mf"

    def __init__(
        self,
        embedding_dim: int = 64,
        learning_rate: float = 0.05,
        reg: float = 0.01,
        epochs: int = 20,
        batch_size: int = 2048,
        seed: int = 42,
    ) -> None:
        super().__init__()
        if embedding_dim <= 0:
            raise ValueError(f"embedding_dim must be positive, got {embedding_dim}")
        if learning_rate <= 0:
            raise ValueError(f"learning_rate must be positive, got {learning_rate}")
        if reg < 0:
            raise ValueError(f"reg must be non-negative, got {reg}")
        if epochs <= 0:
            raise ValueError(f"epochs must be positive, got {epochs}")
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")

        self.embedding_dim = embedding_dim
        self.learning_rate = learning_rate
        self.reg = reg
        self.epochs = epochs
        self.batch_size = batch_size
        self.seed = seed
        self.user_factors: np.ndarray | None = None
        self.item_factors: np.ndarray | None = None
        self.item_bias: np.ndarray | None = None
        self.loss_history: list[float] = []

    def _sample_negatives(self, rng, users: np.ndarray, pos_items: np.ndarray, train_matrix: sp.csr_matrix) -> np.ndarray:
        """Lấy mẫu item âm, đảm bảo không trùng item user đã tương tác trong batch."""
        num_items = self.num_items
        neg = rng.integers(0, num_items, size=len(users))

        # Keep sampling until no clashes with positive items in this batch
        max_attempts = 10
        for attempt in range(max_attempts):
            # Check if any negative equals its corresponding positive
            clash = neg == pos_items
            if not clash.any():
                break
            # Resample only the clashing negatives
            neg[clash] = rng.integers(0, num_items, size=int(clash.sum()))

        # After max_attempts, verify once more and set clashing negatives to a valid alternative
        # If still clashing, find a valid negative by sampling from items NOT in user's history
        clash = neg == pos_items
        if clash.any():
            # For users where we still have a clash, we need to find a valid negative
            # This is more expensive but ensures correctness
            for idx in np.where(clash)[0]:
                u = users[idx]
                # Get all items this user has interacted with
                user_items = set(train_matrix[u].indices)
                # Sample until we find a valid negative
                # If user has interacted with all items, skip this training pair
                if len(user_items) >= num_items:
                    # Mark this as invalid - will be handled in training loop
                    neg[idx] = -1
                else:
                    for _ in range(20):  # Try harder for these edge cases
                        candidate = rng.integers(0, num_items)
                        if candidate not in user_items and candidate != pos_items[idx]:
                            neg[idx] = candidate
                            break
                    else:
                        # Still couldn't find valid negative - mark as invalid
                        neg[idx] = -1

        return neg

    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        rng = np.random.default_rng(self.seed)
        num_users, num_items, d = self.num_users, self.num_items, self.embedding_dim

        coo = train_matrix.tocoo()
        users_all = coo.row.astype(np.int64)
        items_all = coo.col.astype(np.int64)
        n = len(users_all)
        if n == 0:
            raise ValueError("Cannot fit BPR-MF on an empty interaction matrix")

        # Precompute user interaction counts to check if user has interacted with all items
        user_interaction_counts = np.bincount(users_all, minlength=num_users)

        self.user_factors = rng.normal(0, 0.1, (num_users, d)).astype(np.float32)
        self.item_factors = rng.normal(0, 0.1, (num_items, d)).astype(np.float32)
        self.item_bias = np.zeros(num_items, dtype=np.float32)
        self.loss_history = []

        lr, reg = self.learning_rate, self.reg
        P, Q, b = self.user_factors, self.item_factors, self.item_bias

        for _ in range(self.epochs):
            order = rng.permutation(n)
            epoch_loss = 0.0
            valid_pairs = 0  # Count valid training pairs (where negative sampling succeeded)

            for start in range(0, n, self.batch_size):
                sel = order[start : start + self.batch_size]
                u, i = users_all[sel], items_all[sel]

                # Skip users who have interacted with all items (no valid negatives)
                # A user with num_items interactions has seen everything
                mask = user_interaction_counts[u] < num_items
                if not mask.any():
                    continue

                u_valid, i_valid = u[mask], i[mask]
                j = self._sample_negatives(rng, u_valid, i_valid, train_matrix)

                # Filter out invalid negative samples (marked as -1)
                valid_j_mask = j >= 0
                if not valid_j_mask.any():
                    continue  # No valid pairs in this batch

                u_valid, i_valid, j = u_valid[valid_j_mask], i_valid[valid_j_mask], j[valid_j_mask]

                pu, qi, qj = P[u_valid], Q[i_valid], Q[j]
                x = b[i_valid] - b[j] + np.sum(pu * (qi - qj), axis=1)
                coeff = (1.0 / (1.0 + np.exp(np.clip(x, -30, 30)))).astype(np.float32)  # sigmoid(-x)
                epoch_loss += float(np.logaddexp(0.0, -x).sum())
                valid_pairs += len(u_valid)

                c = coeff[:, None]
                np.add.at(P, u_valid, lr * (c * (qi - qj) - reg * pu))
                np.add.at(Q, i_valid, lr * (c * pu - reg * qi))
                np.add.at(Q, j, lr * (-c * pu - reg * qj))
                np.add.at(b, i_valid, lr * (coeff - reg * b[i_valid]))
                np.add.at(b, j, lr * (-coeff - reg * b[j]))

            if valid_pairs > 0:
                self.loss_history.append(epoch_loss / valid_pairs)
            else:
                # If no valid pairs (all users have full catalog), append previous loss or 0
                self.loss_history.append(self.loss_history[-1] if self.loss_history else 0.0)

    def score_batch(self, user_idxs: np.ndarray) -> np.ndarray:
        assert self.user_factors is not None and self.item_factors is not None
        return self.user_factors[user_idxs] @ self.item_factors.T + self.item_bias[None, :]
