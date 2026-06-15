# Regenerate Owen's Desktop DayZ start launchers from admin/map_launch.json.
param(
    [string]$OutputDir = (Join-Path $env:USERPROFILE 'OneDrive\Desktop\games\DayZ')
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$LaunchPath = Join-Path $PSScriptRoot 'map_launch.json'
if (-not (Test-Path $LaunchPath)) { throw "Missing $LaunchPath" }

$Launch = Get-Content $LaunchPath -Raw | ConvertFrom-Json

$DesktopNames = @{
    chernarus = 'start_chernarus.bat'
    enoch     = 'start_Enoch.bat'
    namalsk   = 'start_Namalsk.bat'
    sakhal    = 'start_Sakhal.bat'
    takistan  = 'start_Takistan.bat'
    deerisle  = 'start_deerisle.bat'
    banov     = 'start_banov.bat'
    esseker   = 'start_esseker.bat'
    rostow    = 'start_rostow.bat'
    iztek     = 'start_iztek.bat'
    alteria   = 'start_alteria.bat'
}

$ScheduledRestart = @{
    chernarus = 14390
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

foreach ($entry in $DesktopNames.GetEnumerator() | Sort-Object Name) {
    $map = $entry.Key
    $cfg = $Launch.maps.$map
    if (-not $cfg) { throw "Missing map in admin/map_launch.json: $map" }

    $restartArg = if ($ScheduledRestart.ContainsKey($map)) {
        " -ScheduledRestartSeconds $($ScheduledRestart[$map])"
    } else {
        ""
    }
    $title = ($cfg.title -replace '"', '')
    $target = Join-Path $OutputDir $entry.Value
    $content = @"
@echo off
title $title
cd /d "$Root"
powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\Launch-DayZMap.ps1" -Map $map$restartArg
pause
"@
    Set-Content -LiteralPath $target -Value $content -Encoding ASCII
    Write-Host "Wrote $target"
}
