@echo off
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\bin;C:\Program Files\GitHub CLI;%PATH%"

echo Checking GitHub login...
gh auth status
if errorlevel 1 (
  echo.
  echo Not logged in. Run this first:
  echo   gh auth login
  echo Then run publish-to-github.bat again.
  pause
  exit /b 1
)

echo.
echo Creating GitHub repo and pushing...
gh repo create screen-target-clicker --public --source=. --remote=origin --push
if errorlevel 1 goto :failed

echo.
echo Done. Your repo:
gh repo view --web
pause
exit /b 0

:failed
echo.
echo Push failed. The repo may already exist — try:
echo   gh repo create screen-target-clicker --public --source=. --remote=origin --push
echo Or pick a different name if screen-target-clicker is taken.
pause
exit /b 1
