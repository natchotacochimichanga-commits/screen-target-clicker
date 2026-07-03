@echo off
cd /d "%~dp0"
echo Syncing obfuscated app to repo root and removing clutter...
py scripts\sync_github.py
if errorlevel 1 pause & exit /b 1
echo.
echo Done. Review changes, then commit and push to GitHub.
pause
