#!/usr/bin/env bash
# Wrapper around prepare_amazon.py — set DATA_DIR (required) and optionally
# override the other pipeline parameters below, then run this script.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DATA_DIR="${DATA_DIR:?Set DATA_DIR to the dataset directory, e.g. DATA_DIR=~/blob/raw_datasets/amazon-beauty-2014 ./run_prepare_amazon.sh}"
DATASET_NAME="${DATASET_NAME:-Beauty}"
OUTPUT_SUBDIR="${OUTPUT_SUBDIR:-chatbot}"
RATING_THRESHOLD="${RATING_THRESHOLD:-3.0}"
USER_K="${USER_K:-5}"
ITEM_K="${ITEM_K:-5}"
MAX_HISTORY_LEN="${MAX_HISTORY_LEN:-10}"
MAX_TITLE_LEN="${MAX_TITLE_LEN:-50}"
SIMULATOR_SAMPLE_N="${SIMULATOR_SAMPLE_N:-900}"
SEED="${SEED:-2024}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

python3 "${SCRIPT_DIR}/prepare_amazon.py" \
  --data_dir "${DATA_DIR}" \
  --dataset_name "${DATASET_NAME}" \
  --output_subdir "${OUTPUT_SUBDIR}" \
  --rating_threshold "${RATING_THRESHOLD}" \
  --user_k "${USER_K}" \
  --item_k "${ITEM_K}" \
  --max_history_len "${MAX_HISTORY_LEN}" \
  --max_title_len "${MAX_TITLE_LEN}" \
  --simulator_sample_n "${SIMULATOR_SAMPLE_N}" \
  --seed "${SEED}" \
  --log_level "${LOG_LEVEL}"
