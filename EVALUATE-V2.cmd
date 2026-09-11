@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -u evaluate_v2.py
if errorlevel 1 goto done
".venv\Scripts\python.exe" summarize_v2.py
:done
pause
