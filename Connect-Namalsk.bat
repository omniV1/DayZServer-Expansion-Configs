@echo off
REM Do NOT use steam://connect alone — it can join without Namalsk mods and kicks with LEHS / character_proxies.p3d.
echo.
echo 1. DayZ Launcher - MODS - Presets - select "Owens-Namalsk" - click PLAY
echo 2. If you were kicked before, run admin\reset_namalsk_character.ps1 with server stopped
echo 3. Optional: admin\sync_namalsk_to_client.ps1 then admin\install_namalsk_mod_preset.ps1
echo.
start "" "%LOCALAPPDATA%\DayZ Launcher\DayZLauncher.exe" 2>nul
if errorlevel 1 start "" "C:\Program Files (x86)\Steam\steamapps\common\DayZ\DayZLauncher.exe" 2>nul
timeout /t 3 >nul
start "" steam://run/221100//+connect 127.0.0.1:2502
