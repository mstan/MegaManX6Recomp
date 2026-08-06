@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0COLLECT_FULLSCREEN_DIAGNOSTICS.ps1"
echo.
pause
