@echo off
REM Expansion AI ammo boost — patrols, spatial AI, loadouts
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0admin\apply-ai-ammo.ps1" %*
exit /b %ERRORLEVEL%
