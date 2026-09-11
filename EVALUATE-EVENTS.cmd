@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP-WINDOWS.cmd before evaluation.
    pause
    exit /b 1
)
echo Stop the demo with STOP-DEMO.cmd first to free GPU memory.
".venv\Scripts\python.exe" -u evaluate_events.py --legacy-per-domain
set "evaluationExit=%errorlevel%"
pause
exit /b %evaluationExit%
