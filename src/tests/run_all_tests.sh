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
MAIN_LOG="logs/test_run_${TIMESTAMP}.log"

cd ..

echo "==========================================" | tee -a "$MAIN_LOG"
echo "Running All Tests - $TIMESTAMP" | tee -a "$MAIN_LOG"
echo "==========================================" | tee -a "$MAIN_LOG"

# Run tests in each subdirectory
echo "" | tee -a "$MAIN_LOG"
echo "=== Running Config Tests ===" | tee -a "$MAIN_LOG"
PYTHONPATH=. python -m pytest tests/config/ -v --tb=short --log-cli-level=INFO 2>&1 | tee -a "$MAIN_LOG" || true

echo "" | tee -a "$MAIN_LOG"
echo "=== Running Data Tests ===" | tee -a "$MAIN_LOG"
PYTHONPATH=. python -m pytest tests/data/ -v --tb=short --log-cli-level=INFO 2>&1 | tee -a "$MAIN_LOG" || true

echo "" | tee -a "$MAIN_LOG"
echo "=== Running Agent Tests ===" | tee -a "$MAIN_LOG"
PYTHONPATH=. python -m pytest tests/agent/ -v --tb=short --log-cli-level=INFO 2>&1 | tee -a "$MAIN_LOG" || true

echo "" | tee -a "$MAIN_LOG"
echo "==========================================" | tee -a "$MAIN_LOG"
echo "All tests completed. Log saved to: $MAIN_LOG" | tee -a "$MAIN_LOG"
echo "==========================================" | tee -a "$MAIN_LOG"
