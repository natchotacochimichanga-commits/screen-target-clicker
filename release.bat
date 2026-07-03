@echo off
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\bin;C:\Program Files\GitHub CLI;%PATH%"

set "VERSION=v1.2"
if not "%~1"=="" set "VERSION=%~1"

if not exist "ScreenTargetClicker-Portable.zip" (
  echo Portable zip not found. Run build.bat and package-portable.bat first.
  pause
  exit /b 1
)

echo Publishing %VERSION% to GitHub Releases...
gh release create %VERSION% ScreenTargetClicker-Portable.zip --title "Screen Target Clicker %VERSION%" --generate-notes
if errorlevel 1 (
  echo.
  echo If the release already exists, try:
  echo   gh release upload %VERSION% ScreenTargetClicker-Portable.zip --clobber
  pause
  exit /b 1
)

echo.
echo Done. Latest download:
echo   https://github.com/natchotacochimichanga-commits/screen-target-clicker/releases/latest
pause
