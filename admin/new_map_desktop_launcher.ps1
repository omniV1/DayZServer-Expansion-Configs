# Create a Desktop-style start_<map>.bat for any map in admin/map_launch.json.
param(
    [Parameter(Mandatory = $true)]
    [string]$Map,

    [string]$OutputDir = (Join-Path $env:USERPROFILE 'OneDrive\Desktop\games\DayZ'),

    [switch]$ScheduledRestart,

    [int]$ScheduledRestartSeconds = 14390
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$launchPath = Join-Path $Root 'admin\map_launch.json'
$launch = Get-Content $launchPath -Raw | ConvertFrom-Json
$cfg = $launch.maps.$Map
if (-not $cfg) {
    $known = ($launch.maps.PSObject.Properties.Name -join ', ')
    throw "Unknown map in admin/map_launch.json: $Map. Known maps: $known"
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$out = Join-Path $OutputDir ("start_{0}.bat" -f $Map)
$title = ($cfg.title -replace '"', '')
$restartArg = if ($ScheduledRestart) { " -ScheduledRestartSeconds $ScheduledRestartSeconds" } else { "" }
$content = @"
@echo off
title $title
powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\Launch-DayZMap.ps1" -Map $Map$restartArg
pause
"@

Set-Content -LiteralPath $out -Value $content -Encoding ASCII
Write-Host "Wrote $out"
