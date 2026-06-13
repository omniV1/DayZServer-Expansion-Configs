@echo off
cd /d "%~dp0"
echo Stop any running DayZServer_x64.exe first, then press a key to start all five maps in order...
pause >nul
start "Chernarus" cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File ""%~dp0Launch-DayZMap.ps1"" -Map chernarus"
timeout /t 45 /nobreak >nul
start "Livonia" cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File ""%~dp0Launch-DayZMap.ps1"" -Map enoch"
timeout /t 30 /nobreak >nul
start "Namalsk" cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File ""%~dp0Launch-DayZMap.ps1"" -Map namalsk"
timeout /t 30 /nobreak >nul
start "Sakhal" cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File ""%~dp0Launch-DayZMap.ps1"" -Map sakhal"
timeout /t 45 /nobreak >nul
start "Takistan" cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File ""%~dp0Launch-DayZMap.ps1"" -Map takistan"
echo Started. Wait ~2 min per map, then check LAN or Remote - Favorites.
