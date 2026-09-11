@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP-WINDOWS.cmd before evaluation.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -u evaluate_v2.py --summary
set "evaluationExit=%errorlevel%"
pause
exit /b %evaluationExit%
