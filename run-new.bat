@echo off
cd /d "%~dp0"
if exist "src\main.py" (
  start "" py src\main.py
) else (
  start "" py main.py
)
