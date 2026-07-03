@echo off
cd /d "%~dp0"
if not exist "src\main.py" (
  echo src\ folder not found. You need the local readable source to develop.
  pause
  exit /b 1
)
py -m pip install -r requirements.txt -q
py src\main.py
