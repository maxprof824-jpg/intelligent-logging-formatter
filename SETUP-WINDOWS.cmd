@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0SETUP.ps1"
set "setupResult=%ERRORLEVEL%"
pause
exit /b %setupResult%
