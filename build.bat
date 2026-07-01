@echo off
cd /d "%~dp0"
echo Installing dependencies...
py -m pip install -r requirements.txt pyinstaller -q

echo Closing any running copy of the app...
taskkill /IM ScreenTargetClicker.exe /F >nul 2>&1

echo Building portable folder...
py -m PyInstaller --noconfirm --clean ScreenTargetClicker.spec
if errorlevel 1 goto :failed

echo Ensuring OpenCV config files are bundled...
for /f "delims=" %%P in ('py -c "import cv2, os; print(os.path.dirname(cv2.__file__))"') do set CV2_DIR=%%P
copy /Y "%CV2_DIR%\config.py" "dist\ScreenTargetClicker\_internal\cv2\" >nul
copy /Y "%CV2_DIR%\config-3.py" "dist\ScreenTargetClicker\_internal\cv2\" >nul

echo.
echo Done. Portable app folder:
echo   dist\ScreenTargetClicker\
pause
exit /b 0

:failed
echo.
echo Build failed. Close ScreenTargetClicker.exe if it is running, then try again.
pause
exit /b 1
