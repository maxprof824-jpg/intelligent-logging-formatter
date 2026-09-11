@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP-WINDOWS.cmd first to install this project's environment.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" app_v2.py --base
set "demoResult=%ERRORLEVEL%"
pause
exit /b %demoResult%
