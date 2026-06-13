# Takistan join prep: sync map mod, verify mission + mod order.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent

Write-Host '1/3 Sync @TakistanPlus from Steam Workshop...'
& (Join-Path $PSScriptRoot 'sync_takistan_plus.ps1')

$mp = Join-Path $root 'mpmissions'
$link = Join-Path $mp 'dayzOffline.TakistanPlus'
if (-not (Test-Path $link)) {
    $src = Join-Path $mp 'dayzOffline.Takistan'
    if (-not (Test-Path $src)) {
        Write-Host 'Missing mission folder. Run: python admin\install_takistan_mission.py' -ForegroundColor Red
        exit 1
    }
    cmd /c mklink /J "$link" "$src" | Out-Null
    Write-Host "Linked mission: dayzOffline.TakistanPlus -> dayzOffline.Takistan"
}

Write-Host '2/4 Takistan Expansion spawn + AI (towns 1-2 AI, map-native coords)...'
python (Join-Path $root 'admin\build_map_expansion.py') takistan
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '3/4 Mod order (last two must be @Dabs Framework then @TakistanPlus):'
$mods = (Get-Content (Join-Path $PSScriptRoot 'takistan_mods.txt') -Raw).Trim().Split(';')
$tail = $mods[-2..-1] -join ' -> '
Write-Host "  ... -> $tail"

Write-Host '4/4 After server start, run: admin\check_takistan.ps1'
Write-Host ''
Write-Host 'Client: same mods as Chernarus + @TakistanPlus (2563233742), Dabs immediately before TakistanPlus.'
Write-Host 'Start: Launch-DayZMap.ps1 -Map takistan   Join: 127.0.0.1:2702:27020'
