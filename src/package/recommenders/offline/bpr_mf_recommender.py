from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from ..shared.device import get_device
from ..shared.recommender import Recommender, _topk_row_exact


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

    @staticmethod
    def _is_positive(train_matrix: sp.csr_matrix, users: np.ndarray, items: np.ndarray) -> np.ndarray:
        """True where user ``users[i]`` has interacted with item ``items[i]`` (vectorised CSR lookup)."""
        return np.asarray(train_matrix[users, items]).ravel() != 0

    def _sample_negatives(self, rng, users: np.ndarray, pos_items: np.ndarray, train_matrix: sp.csr_matrix) -> np.ndarray:
        """One negative item per row: an item the user has NOT interacted with (any of their positives, not just
        the paired one). Returns -1 for a row only when the user has interacted with every item.

        Step 1: cheap vectorised rejection sampling (a few rounds). Step 2: for the rare rows still clashing,
        draw exactly from that user's complement, so the result is always valid and there is no unbounded loop.
        ``pos_items`` is kept for API compatibility: a user's positives already include it.
        """
        num_items = self.num_items
        neg = rng.integers(0, num_items, size=len(users))
        for _ in range(10):
            clash = self._is_positive(train_matrix, users, neg)
            if not clash.any():
                return neg
            neg[clash] = rng.integers(0, num_items, size=int(clash.sum()))

        indptr, indices = train_matrix.indptr, train_matrix.indices
        for idx in np.where(self._is_positive(train_matrix, users, neg))[0]:
            u = users[idx]
            free = np.setdiff1d(np.arange(num_items), indices[indptr[u] : indptr[u + 1]])
            neg[idx] = rng.choice(free) if len(free) else -1
        return neg

    def _fit(self, train_matrix: sp.csr_matrix) -> None:
        try:
            import torch  # noqa: F401
        except ImportError:
            self._fit_numpy(train_matrix)
            return
        self._fit_torch(train_matrix)

    def _fit_torch(self, train_matrix: sp.csr_matrix) -> None:
        """BPR-MF training on torch (CUDA when available, else CPU).

        Memory layout: item factors + bias live on the compute device; user
        factors stay on CPU because 23M x 64 fp32 (~5.9GB) exceeds the 4GB
        GPU. Each batch gathers the needed user rows on CPU, moves the small
        (batch, d) tensors to the device, and writes the user-factor deltas
        back — ~0.5MB transferred per batch instead of materialising all
        user factors on the GPU.
        """
        import torch

        rng = np.random.default_rng(self.seed)
        num_users, num_items, d = self.num_users, self.num_items, self.embedding_dim
        device = get_device()

        coo = train_matrix.tocoo()
        users_all = coo.row.astype(np.int64)
        items_all = coo.col.astype(np.int64)
        n = len(users_all)
        if n == 0:
            raise ValueError("Cannot fit BPR-MF on an empty interaction matrix")

        user_interaction_counts = np.bincount(users_all, minlength=num_users)

        # Init from the numpy RNG so runs are reproducible from `seed` alone
        # (torch's global RNG is not seeded by it).
        P_t = torch.from_numpy(
            rng.normal(0, 0.1, (num_users, d)).astype(np.float32))
        Q = torch.from_numpy(
            rng.normal(0, 0.1, (num_items, d)).astype(np.float32)).to(device)
        b = torch.zeros(num_items, dtype=torch.float32, device=device)
        self.loss_history = []
        self.__dict__.pop("_topk_cache", None)

        lr, reg = self.learning_rate, self.reg

        # CUDA index_add_ is atomic/add-order nondeterministic; deterministic
        # mode makes same-seed runs bitwise reproducible (contract test).
        prev_deterministic = torch.are_deterministic_algorithms_enabled()
        torch.use_deterministic_algorithms(True)
        try:
            self._fit_torch_epochs(train_matrix, rng, P_t, Q, b, device, lr, reg)
        finally:
            torch.use_deterministic_algorithms(prev_deterministic)

        self.user_factors = P_t.numpy()
        self.item_factors = Q.detach().cpu().numpy()
        self.item_bias = b.detach().cpu().numpy()

    def _fit_torch_epochs(self, train_matrix, rng, P_t, Q, b, device, lr, reg) -> None:
        import torch

        num_users, num_items = self.num_users, self.num_items
        coo = train_matrix.tocoo()
        users_all = coo.row.astype(np.int64)
        items_all = coo.col.astype(np.int64)
        n = len(users_all)
        user_interaction_counts = np.bincount(users_all, minlength=num_users)

        for _ in range(self.epochs):
            order = rng.permutation(n)
            epoch_loss = torch.zeros((), dtype=torch.float32, device=device)
            valid_pairs = 0

            for start in range(0, n, self.batch_size):
                sel = order[start : start + self.batch_size]
                u, i = users_all[sel], items_all[sel]

                mask = user_interaction_counts[u] < num_items
                if not mask.any():
                    continue

                u_valid, i_valid = u[mask], i[mask]
                j = self._sample_negatives(rng, u_valid, i_valid, train_matrix)

                valid_j_mask = j >= 0
                if not valid_j_mask.any():
                    continue

                u_valid = u_valid[valid_j_mask]
                i_valid = i_valid[valid_j_mask]
                j = j[valid_j_mask]

                u_t = torch.from_numpy(u_valid)
                i_t = torch.from_numpy(i_valid).to(device)
                j_t = torch.from_numpy(j).to(device)
                with torch.no_grad():
                    pu = P_t[u_t].to(device)
                    qi, qj = Q[i_t], Q[j_t]
                    x = b[i_t] - b[j_t] + (pu * (qi - qj)).sum(dim=1)
                    coeff = torch.sigmoid(-x)
                    epoch_loss = epoch_loss + torch.nn.functional.softplus(-x).sum()
                    valid_pairs += len(u_valid)

                    c = coeff[:, None]
                    dpu = lr * (c * (qi - qj) - reg * pu)
                    Q.index_add_(0, i_t, lr * (c * pu - reg * qi))
                    Q.index_add_(0, j_t, lr * (-c * pu - reg * qj))
                    b.index_add_(0, i_t, lr * (coeff - reg * b[i_t]))
                    b.index_add_(0, j_t, lr * (-coeff - reg * b[j_t]))
                    P_t.index_add_(0, u_t, dpu.cpu())

            if valid_pairs > 0:
                self.loss_history.append(float(epoch_loss.item()) / valid_pairs)
            else:
                self.loss_history.append(self.loss_history[-1] if self.loss_history else 0.0)

    def _fit_numpy(self, train_matrix: sp.csr_matrix) -> None:
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
        self.__dict__.pop("_topk_cache", None)

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

    # Fused top-k: scores are computed in (users x item-tile) blocks on the
    # compute device so the full users x items matrix is never materialised.
    # Tile sizes keep each block ~134MB fp32 — fits the 4GB GPU alongside the
    # item factor table (~0.7GB); CPU fallback uses the same torch path.
    _TOPK_USER_CHUNK = 256
    _TOPK_ITEM_TILE = 131_072
    _TOPK_MAX_K = 65_536

    def _recommend_topk(self, user_idxs, k, exclude):
        if (self.user_factors is None or self.item_factors is None
                or self.item_bias is None or self.train_matrix is None):
            return None
        if k > self._TOPK_MAX_K:
            return None
        try:
            import torch
        except ImportError:
            return None

        device = get_device()
        cache = self.__dict__.setdefault("_topk_cache", {})
        if cache.get("device") != device:
            cache.clear()
            cache["device"] = device
        if "Q" not in cache:
            cache["Q"] = torch.as_tensor(
                np.ascontiguousarray(self.item_factors), device=device)
            cache["bias"] = torch.as_tensor(
                np.ascontiguousarray(self.item_bias), device=device)
            cache["pop_counts"] = np.asarray(
                self.train_matrix.sum(axis=0)).ravel().astype(np.float32)
        Q, bias = cache["Q"], cache["bias"]
        n_items = self.num_items
        users = np.asarray(user_idxs, dtype=np.int64).ravel()
        result = np.full((len(users), k), -1, dtype=np.int64)

        for c0 in range(0, len(users), self._TOPK_USER_CHUNK):
            u_chunk = users[c0:c0 + self._TOPK_USER_CHUNK]
            b = len(u_chunk)
            U = torch.as_tensor(
                np.ascontiguousarray(self.user_factors[u_chunk]), device=device)

            # Excluded (user_pos_in_chunk, item) pairs for this chunk.
            ex_rows = ex_cols = None
            if exclude is not None:
                ex = exclude[u_chunk].tocoo()
                nz = ex.data != 0
                ex_rows = torch.as_tensor(ex.row[nz], device=device)
                ex_cols = torch.as_tensor(ex.col[nz], device=device)

            best_s = torch.full((b, k), -float("inf"), device=device)
            best_i = torch.full((b, k), -1, device=device, dtype=torch.int64)
            max_valid = torch.full((b,), -float("inf"), device=device)
            min_valid = torch.full((b,), float("inf"), device=device)

            for t0 in range(0, n_items, self._TOPK_ITEM_TILE):
                t1 = min(t0 + self._TOPK_ITEM_TILE, n_items)
                S = U @ Q[t0:t1].T + bias[t0:t1]
                if ex_rows is not None and len(ex_rows):
                    m = (ex_cols >= t0) & (ex_cols < t1)
                    if bool(m.any()):
                        S[ex_rows[m], ex_cols[m] - t0] = -float("inf")
                # Track min/max valid score per user for the all-zero check.
                t_max = S.max(dim=1).values
                t_min = S.masked_fill(S == -float("inf"), float("inf")).min(dim=1).values
                max_valid = torch.maximum(max_valid, t_max)
                min_valid = torch.minimum(min_valid, t_min)
                kk = min(k, t1 - t0)
                s, i = torch.topk(S, kk, dim=1)
                gi = i + t0
                all_s = torch.cat([best_s, s], dim=1)
                all_i = torch.cat([best_i, gi], dim=1)
                ms, mi = torch.topk(all_s, k, dim=1)
                best_s = ms
                best_i = torch.gather(all_i, 1, mi)

            bs = best_s.cpu().numpy()
            bi = best_i.cpu().numpy()
            mv = max_valid.cpu().numpy()
            nv = min_valid.cpu().numpy()
            has_valid = mv > -np.inf
            all_zero = has_valid & (mv == 0.0) & (nv == 0.0)

            for j in range(b):
                if all_zero[j]:
                    # Every non-excluded score is exactly 0 -> popularity
                    # fallback, identical to the dense path semantics.
                    row = cache["pop_counts"].copy()
                    if exclude is not None:
                        exu = exclude[u_chunk[j]:u_chunk[j] + 1].tocoo()
                        nzu = exu.data != 0
                        row[exu.col[nzu]] = -np.inf
                    ranked = _topk_row_exact(row.astype(np.float32), k)
                    valid = row[ranked] > -np.inf
                    result[c0 + j, : int(valid.sum())] = ranked[valid]
                else:
                    valid = bs[j] > -np.inf
                    result[c0 + j, : int(valid.sum())] = bi[j][valid]
        return result
