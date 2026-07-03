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

if not exist "website\downloads" mkdir "website\downloads"

echo.
echo Created: %CD%\%ZIP%
echo.
echo Publish to GitHub Releases:
echo   release.bat v1.2
echo.
echo Or upload manually:
echo   gh release upload v1.2 %ZIP% --clobber
pause
