@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0vinhomes-api\scripts\launch_connected.ps1"
if errorlevel 1 (
  echo Khong khoi dong duoc. Hay kiem tra cau hinh database va dang nhap that.
  pause
  exit /b 1
)
