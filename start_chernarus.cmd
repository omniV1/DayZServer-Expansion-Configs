@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0admin\apply_lan_query_ports.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-DayZMap.ps1" -Map chernarus -ScheduledRestartSeconds 14390
