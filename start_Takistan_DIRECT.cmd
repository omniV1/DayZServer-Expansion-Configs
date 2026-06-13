@echo off
title Owens DayZ Takistan Server
cd /d "%~dp0"
echo Use Launch-DayZMap.ps1 -Map takistan (port 2702, profiles_takistan, full Chernarus mods).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-DayZMap.ps1" -Map takistan
pause
