@echo off
REM Run all tests and save results to log files

setlocal enabledelayedexpansion

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Get current timestamp for log filename
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%
set MAIN_LOG=logs\test_run_%TIMESTAMP%.log

echo ========================================== > %MAIN_LOG%
echo Running All Tests - %TIMESTAMP% >> %MAIN_LOG%
echo ========================================== >> %MAIN_LOG%

REM Run tests in each subdirectory
echo. >> %MAIN_LOG%
echo === Running Config Tests === >> %MAIN_LOG%
set PYTHONPATH=.
python -m pytest tests/config/ -v --tb=short --log-cli-level=INFO >> %MAIN_LOG% 2>&1

echo. >> %MAIN_LOG%
echo === Running Data Tests === >> %MAIN_LOG%
python -m pytest tests/data/ -v --tb=short --log-cli-level=INFO >> %MAIN_LOG% 2>&1

echo. >> %MAIN_LOG%
echo === Running Agent Tests === >> %MAIN_LOG%
python -m pytest tests/agent/ -v --tb=short --log-cli-level=INFO >> %MAIN_LOG% 2>&1

echo. >> %MAIN_LOG%
echo ========================================== >> %MAIN_LOG%
echo All tests completed. Log saved to: %MAIN_LOG% >> %MAIN_LOG%
echo ========================================== >> %MAIN_LOG%

echo All tests completed. Log saved to: %MAIN_LOG%
