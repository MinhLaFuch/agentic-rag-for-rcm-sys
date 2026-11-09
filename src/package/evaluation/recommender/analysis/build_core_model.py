"""Load train-core CF and expose it in the global evaluation index space."""
import numpy as np
from scipy import sparse
from ....recommenders import ItemKNNRecommender, build_interaction_matrix
from ....recommenders.shared.load_item_knn import load_item_knn
from ....recommenders.shared.fit_provenance import fit_provenance
from ....recommenders import item_knn_data_hash
from .core_inputs import core_inputs


def build_core_model(paths, eval_on, neighbors, history, user2id, item2id):
    """Return None for legacy tags; validate/load the compact cache for v2 tags.

    Similarity and popularity are learned only from train-core. Scoring and seen
    exclusion use all pre-target history, including users outside the fit core.
    Test also keeps the frozen train-core, matching Stage 4's current protocol.
    """
    inputs = core_inputs(paths, user2id, item2id)
    if inputs is None:
        return None
    pairs, users, items, _, global_items = inputs
    context = dict(user2id=users, item2id=items, eval_on=eval_on,
                   tag=paths.tag, fit_splits=["train_core"])
    cache = paths.item_knn_path(eval_on)
    if cache.is_file():
        model = load_item_knn(cache, neighbors, pairs, **context)
        status = "validated_train_core_cache"
    else:
        model = ItemKNNRecommender(neighbors).fit(pairs)
        status = "fit_fresh_train_core"
    model._evaluation_fit_provenance = fit_provenance(pairs, **context)
    model._fit_data_hash = item_knn_data_hash(pairs)
    model._evaluation_artifact_status = status
    coo = model.similarity.tocoo()
    model.similarity = sparse.csr_matrix(
        (coo.data, (global_items[coo.row], global_items[coo.col])),
        shape=(len(item2id), len(item2id)))
    popularity = np.zeros(len(item2id), dtype=np.float64)
    popularity[global_items] = model.scores
    model.scores = popularity
    model.num_items = len(item2id)
    model.ranked_items = np.argsort(-popularity, kind="stable")
    model.user_items = build_interaction_matrix(history, len(user2id), len(item2id))
    return model
