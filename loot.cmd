@echo off
REM Quick launcher: DayZServer\loot.cmd [args]
REM Examples:
REM   loot.cmd
REM   loot.cmd -Action status
REM   loot.cmd -Action all -Preset high
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0admin\apply-loot.ps1" %*
exit /b %ERRORLEVEL%
