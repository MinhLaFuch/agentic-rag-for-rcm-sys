#!/usr/bin/env bash
# EDA interaction trên review thô (resource/raw/<Domain>.jsonl.gz), mặc định mọi domain trong data.yaml.
#   bash scripts/sh/run_eda.sh
#   bash scripts/sh/run_eda.sh --domain Video_Games
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
"$PYTHON" scripts/py/run_eda.py "$@"
