#!/usr/bin/env bash
# Wrapper around prepare_movielens.py — set DATA_DIR and OUTPUT_DIR (required)
# and optionally override the other pipeline parameters below, then run this script.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DATA_DIR="${DATA_DIR:?Set DATA_DIR to the dataset directory, e.g. DATA_DIR=~/blob/raw_datasets/ml-10m/original/ml-10M100K OUTPUT_DIR=~/blob/raw_datasets/ml-10m/chatbot ./run_prepare_movielens.sh}"
OUTPUT_DIR="${OUTPUT_DIR:?Set OUTPUT_DIR to the directory splits/movies/jsonl outputs are written to}"
SUFFIX="${SUFFIX:-.csv}"
RATING_THRESHOLD="${RATING_THRESHOLD:-3.0}"
USER_K="${USER_K:-5}"
ITEM_K="${ITEM_K:-5}"
MAX_HISTORY_LEN="${MAX_HISTORY_LEN:-10}"
MAX_TITLE_LEN="${MAX_TITLE_LEN:-50}"
SIMULATOR_SAMPLE_N="${SIMULATOR_SAMPLE_N:-900}"
ONE_TURN_N_USER="${ONE_TURN_N_USER:-500}"
SEED="${SEED:-2024}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

python3 "${SCRIPT_DIR}/prepare_movielens.py" \
  --data_dir "${DATA_DIR}" \
  --output_dir "${OUTPUT_DIR}" \
  --suffix "${SUFFIX}" \
  --rating_threshold "${RATING_THRESHOLD}" \
  --user_k "${USER_K}" \
  --item_k "${ITEM_K}" \
  --max_history_len "${MAX_HISTORY_LEN}" \
  --max_title_len "${MAX_TITLE_LEN}" \
  --simulator_sample_n "${SIMULATOR_SAMPLE_N}" \
  --one_turn_n_user "${ONE_TURN_N_USER}" \
  --seed "${SEED}" \
  --log_level "${LOG_LEVEL}"
