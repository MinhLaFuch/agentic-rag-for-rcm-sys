#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
SPLITS_DIR="data/splits/multi_domain"
MODELS="popularity,item_knn,bpr_mf"
KS=""                                     # e.g. "5,10,20"; empty = default
SELECTION_METRIC=""                       # e.g. "ndcg@10"; empty = tuning.selection_metric
RUN_FINAL_TEST=false                      # true = refit winner on train+val and score TEST once
EXPERIMENTS_DIR="experiments"
# ====================================================
ARGS=(--splits-dir "$SPLITS_DIR" --models "$MODELS" --experiments-dir "$EXPERIMENTS_DIR")
[[ -n "$KS" ]] && ARGS+=(--ks "$KS")
[[ -n "$SELECTION_METRIC" ]] && ARGS+=(--selection-metric "$SELECTION_METRIC")
[[ "$RUN_FINAL_TEST" == true ]] && ARGS+=(--run-final-test)
"$PYTHON" scripts/tune_baselines.py "${ARGS[@]}"
