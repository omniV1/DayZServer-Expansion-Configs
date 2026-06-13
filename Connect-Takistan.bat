@echo off
REM Same mod stack as Chernarus (admin/chernarus_mods.txt) plus @TakistanPlus after @Dabs Framework.
echo.
echo 1. DayZ Launcher - MODS - enable the same mods as Chernarus PLUS @TakistanPlus (Workshop 2563233742)
echo 2. @Dabs Framework must load BEFORE @TakistanPlus
echo 3. Start server: Launch-DayZMap.ps1 -Map takistan  (mission dayzOffline.TakistanPlus)
echo 4. Optional: admin\install_takistan_mod_preset.ps1  (Owens-Takistan preset)
echo.
start "" "%LOCALAPPDATA%\DayZ Launcher\DayZLauncher.exe" 2>nul
if errorlevel 1 start "" "C:\Program Files (x86)\Steam\steamapps\common\DayZ\DayZLauncher.exe" 2>nul
timeout /t 3 >nul
start "" steam://run/221100//+connect 127.0.0.1:2702:27020
