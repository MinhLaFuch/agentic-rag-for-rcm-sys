#!/bin/bash
# Run all tests and save results to log files

set -e

# Change to src directory where tests are located
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -f "../../.venv/bin/activate" ]; then
    source "../../.venv/bin/activate"
elif [ -f "../../.venv/Scripts/activate" ]; then
    source "../../.venv/Scripts/activate"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Get current timestamp for log filename
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
MAIN_LOG="$PWD/logs/test_run_${TIMESTAMP}.log"  # absolute: survives the `cd ..` below; test logs live in tests/logs/
RESULTS_FILE="$PWD/logs/test_results_${TIMESTAMP}.md"  # input/output of EVERY test in one file (see tests/results_report.py)

cd ..

echo "==========================================" | tee -a "$MAIN_LOG"
echo "Running All Tests - $TIMESTAMP" | tee -a "$MAIN_LOG"
echo "==========================================" | tee -a "$MAIN_LOG"

# One pytest run over every folder (config, data, agent, ...) so there is exactly ONE results file
echo "" | tee -a "$MAIN_LOG"
PYTHONPATH=. python -m pytest tests/ -v --tb=short --log-cli-level=INFO --results-file="$RESULTS_FILE" 2>&1 | tee -a "$MAIN_LOG" || true

echo "" | tee -a "$MAIN_LOG"
echo "==========================================" | tee -a "$MAIN_LOG"
echo "All tests completed. Log saved to: $MAIN_LOG" | tee -a "$MAIN_LOG"
echo "Per-test input/output saved to: $RESULTS_FILE" | tee -a "$MAIN_LOG"
echo "==========================================" | tee -a "$MAIN_LOG"
