@echo off
REM Apply AI War Zones for the map you are starting.
REM Example: warzones.cmd enoch
if "%~1"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0admin\apply_warzones.py" --list
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0admin\apply_warzones.py" --build
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0admin\apply_warzones.py" %*
exit /b %ERRORLEVEL%
