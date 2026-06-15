# Recover imported community map configs, validate cleanup, and smoke test.
param(
    [string]$Map = 'rostow',

    [int]$TimeoutSeconds = 300,

    [string]$QueryHost = '127.0.0.1',

    [switch]$StopExisting,

    [switch]$SkipSmoke
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$ImportedMaps = @('deerisle', 'banov', 'esseker', 'rostow', 'iztek', 'alteria')

if ($Map -ne 'all-imported' -and ($ImportedMaps -notcontains $Map)) {
    throw "Map must be one of: $($ImportedMaps -join ', '), or all-imported"
}

Set-Location $Root

if ($StopExisting) {
    $running = Get-Process DayZServer_x64 -ErrorAction SilentlyContinue
    if ($running) {
        $ids = ($running | ForEach-Object { $_.Id }) -join ', '
        Write-Host "Stopping existing DayZServer_x64.exe process(es): $ids"
        $running | Stop-Process -Force
        Start-Sleep -Seconds 3
    }
} elseif (Get-Process DayZServer_x64 -ErrorAction SilentlyContinue) {
    Write-Warning "DayZServer_x64.exe is running. Recovery will continue, but smoke testing may fail unless you stop it or rerun with -StopExisting."
}

Write-Host "Sanitizing imported Expansion generated folders and storage..."
python admin\sanitize_imported_expansion.py --wipe-storage
if ($LASTEXITCODE -ne 0) { throw "sanitize_imported_expansion.py failed" }

Write-Host "Tuning imported player spawns..."
python admin\tune_player_spawns.py
if ($LASTEXITCODE -ne 0) { throw "tune_player_spawns.py failed" }

Write-Host "Applying imported CE safety..."
python admin\tune_imported_ce_safety.py
if ($LASTEXITCODE -ne 0) { throw "tune_imported_ce_safety.py failed" }

Write-Host "Validating imported map cleanup..."
python admin\validate_imported_maps.py
if ($LASTEXITCODE -ne 0) { throw "validate_imported_maps.py failed" }

if (-not $SkipSmoke) {
    if ($Map -eq 'all-imported') {
        powershell -ExecutionPolicy Bypass -File admin\smoke_test_maps.ps1 -Map all-imported -TimeoutSeconds $TimeoutSeconds -QueryHost $QueryHost
    } else {
        powershell -ExecutionPolicy Bypass -File admin\smoke_test_map.ps1 -Map $Map -TimeoutSeconds $TimeoutSeconds -QueryHost $QueryHost
    }
    if ($LASTEXITCODE -ne 0) { throw "Smoke test failed" }

    Write-Host "Cleaning up generated imported-map folders/storage after smoke test..."
    python admin\sanitize_imported_expansion.py --wipe-storage
    if ($LASTEXITCODE -ne 0) { throw "post-smoke sanitize_imported_expansion.py failed" }
    python admin\validate_imported_maps.py
    if ($LASTEXITCODE -ne 0) { throw "post-smoke validate_imported_maps.py failed" }
}

Write-Host "Imported map recovery complete for $Map."
