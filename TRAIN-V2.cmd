@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -u train.py --data-dir data-v2 --max-length 4096 --output runs/adapter-v2
pause
