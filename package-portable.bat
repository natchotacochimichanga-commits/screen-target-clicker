@echo off
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\bin;C:\Program Files\GitHub CLI;%PATH%"

if not exist "dist\ScreenTargetClicker\ScreenTargetClicker.exe" (
  echo Portable build not found. Run build.bat first.
  pause
  exit /b 1
)

set "ZIP=ScreenTargetClicker-Portable.zip"
if exist "%ZIP%" del /f "%ZIP%"

echo Creating %ZIP% ...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\ScreenTargetClicker\*' -DestinationPath '%ZIP%' -Force"

if errorlevel 1 (
  echo Failed to create zip.
  pause
  exit /b 1
)

echo.
echo Created: %CD%\%ZIP%
echo Upload with: gh release upload v1.0 %ZIP% --clobber
pause
