@echo off
REM Run config tests and save results to log file

setlocal enabledelayedexpansion

REM Run from this folder regardless of where the script is invoked from (logs go to tests\logs)
cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist ..\logs mkdir ..\logs

REM Get current timestamp for log filename
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%
set LOG_FILE=..\logs\config_tests_%TIMESTAMP%.log

echo ========================================== > %LOG_FILE%
echo Running Config Tests - %TIMESTAMP% >> %LOG_FILE%
echo ========================================== >> %LOG_FILE%

set PYTHONPATH=..\..
python -m pytest . -v --tb=short --log-cli-level=INFO >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo Config tests completed. Log saved to: %LOG_FILE% >> %LOG_FILE%

echo Config tests completed. Log saved to: %LOG_FILE%
