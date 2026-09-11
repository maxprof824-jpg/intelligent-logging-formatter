@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0TRAIN-V2.ps1" %*
set "trainResult=%ERRORLEVEL%"
pause
exit /b %trainResult%
