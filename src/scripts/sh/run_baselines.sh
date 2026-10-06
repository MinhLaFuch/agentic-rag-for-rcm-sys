#!/usr/bin/env bash
# Chạy baseline trên splits của stage 3. Models/ks/seed: baselines.yaml, recommendation_metrics.yaml.
#   bash scripts/sh/run_baselines.sh
#   bash scripts/sh/run_baselines.sh --eval-on test --models popularity,item_knn
#   TAG=vg_toys bash scripts/sh/run_baselines.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
"$PYTHON" scripts/py/run_baselines.py ${TAG:+--tag "$TAG"} "$@"
