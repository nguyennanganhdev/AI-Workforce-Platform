@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0vinhomes-api\scripts\launch_demo.ps1"
if errorlevel 1 (
  echo.
  echo Khong khoi dong duoc demo. Xem thong bao loi phia tren.
  pause
  exit /b 1
)
echo.
echo Demo dang chay: http://localhost:8000/demo/ui
echo Co the dong cua so nay. API va database van chay.
timeout /t 5 >nul
exit /b 0
