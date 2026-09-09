@echo off
setlocal
cd /d "%~dp0"

set "PATCH_URL=https://raw.githubusercontent.com/terry27310952-arch/ai-pd-studio/main/ict11-stable-v44/stable_patch.ps1"
set "PATCH_FILE=%TEMP%\ict11_stable_patch_v44.ps1"

echo [ICT11] Downloading stable playback patch...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing -Uri '%PATCH_URL%' -OutFile '%PATCH_FILE%'"
if errorlevel 1 (
  echo.
  echo Patch download failed.
  pause
  exit /b 1
)

echo [ICT11] Patching OPEN_DIRECT.html...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PATCH_FILE%" -Target "%CD%"
if errorlevel 1 (
  echo.
  echo Patch failed. Make sure this BAT is inside the extracted ICT11 v4.3 folder.
  pause
  exit /b 1
)

endlocal
