@echo off
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\bin;C:\Program Files\GitHub CLI;%PATH%"

echo Installing build dependencies...
py -m pip install -r requirements.txt pyinstaller pyarmor opencv-python-headless -q

echo Closing any running copy of the app...
taskkill /IM ScreenTargetClicker.exe /F >nul 2>&1

echo Preparing obfuscated release source...
py scripts\prepare_release.py
if errorlevel 1 goto :failed

set "STC_BUILD_SRC=%CD%\build\release_src"
echo Building portable folder from protected source...
py -m PyInstaller --noconfirm --clean ScreenTargetClicker.spec
if errorlevel 1 goto :failed

echo Ensuring OpenCV config files are bundled...
for /f "delims=" %%P in ('py -c "import cv2, os; print(os.path.dirname(cv2.__file__))"') do set CV2_DIR=%%P
copy /Y "%CV2_DIR%\config.py" "dist\ScreenTargetClicker\_internal\cv2\" >nul
copy /Y "%CV2_DIR%\config-3.py" "dist\ScreenTargetClicker\_internal\cv2\" >nul

echo Removing non-essential portable files...
py scripts\prune_portable.py dist\ScreenTargetClicker
if errorlevel 1 goto :failed

set "STC_BUILD_SRC="
echo.
echo Done. Protected portable app folder:
echo   dist\ScreenTargetClicker\
pause
exit /b 0

:failed
set "STC_BUILD_SRC="
echo.
echo Build failed. Close ScreenTargetClicker.exe if it is running, then try again.
pause
exit /b 1
