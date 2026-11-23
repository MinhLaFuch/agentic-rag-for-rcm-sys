"""Stage timing probe for run_baselines --eval-on validation.
Replicates run_baselines.py stages with timestamps to find the bottleneck.
Run: .venv/Scripts/python.exe -u investigations/baseline_stage_timing.py
"""
import time

t0 = time.time()
def lap(msg):
    print(f"[{time.time()-t0:8.1f}s] {msg}", flush=True)

from package.config import get_data_paths, load_config
from package.data.manifest import verify_tag_manifest
from package.data.mapping import load_mappings
from package.data.split import infer_matrix_shape, load_splits
from package.evaluation.recommender.analysis.core_inputs import core_inputs
from package.evaluation.recommender.analysis.global_core_pairs import global_core_pairs
from package.evaluation.recommender.config import select_fit_target
from package.recommenders.shared import build_interaction_matrix, build_model

lap("imports done")
paths = get_data_paths()
verify_tag_manifest(paths)
lap("manifest verified")
train, val, test = load_splits(str(paths.splits_dir))
lap(f"splits loaded: train={len(train)} val={len(val)} test={len(test)}")
num_users, num_items = infer_matrix_shape(train, val, test)
lap(f"matrix shape: {num_users}x{num_items}")
fit_df, target_df = select_fit_target(train, val, test, "validation")
lap(f"fit_df={len(fit_df)} target_df={len(target_df)}")
fit_matrix = build_interaction_matrix(fit_df, num_users, num_items)
lap(f"fit_matrix nnz={fit_matrix.nnz}")
target_matrix = build_interaction_matrix(target_df, num_users, num_items)
lap(f"target_matrix nnz={target_matrix.nnz}")
user2id, item2id = load_mappings(paths.mapped_dir)
lap("mappings loaded")
core = core_inputs(paths, user2id, item2id)
lap(f"core_inputs: {core is not None}")
if core is not None:
    gp = global_core_pairs(core)
    lap(f"global_core_pairs rows={len(gp)}")
    training_matrix = build_interaction_matrix(gp, num_users, num_items)
    lap(f"training_matrix nnz={training_matrix.nnz}")
else:
    training_matrix = fit_matrix

model_cfg = load_config("eval/baselines")["baselines"]
for name in [str(m).strip() for m in model_cfg["models"] if str(m).strip()]:
    lap(f"building model {name}")
    model = build_model(name, model_cfg)
    tm = time.time()
    model.fit(training_matrix)
    lap(f"  {name} fit done in {time.time()-tm:.1f}s")
    from package.evaluation.recommender.core import evaluate_recommender
    te = time.time()
    ks = load_config("eval/recommendation_metrics")["recommendation_metrics"]["k_values"]
    sparse_max = load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"]
    result = evaluate_recommender(model, fit_matrix, target_matrix, ks, sparse_max=sparse_max)
    lap(f"  {name} eval done in {time.time()-te:.1f}s")

lap("ALL DONE")
