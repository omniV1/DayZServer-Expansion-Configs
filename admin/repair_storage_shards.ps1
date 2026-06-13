# Targeted persistence repair: backup and remove corrupt dynamic_*.001/.002 shards.
# Does not wipe full storage_1. Run with server STOPPED.

$ServerRoot = Split-Path $PSScriptRoot -Parent
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path $PSScriptRoot "backups\storage_shards_$Stamp"

$Missions = @(
    "dayzOffline.chernarusplus",
    "dayzOffline.enoch",
    "dayzOffline.sakhal",
    "regular.namalsk"
)

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

foreach ($mission in $Missions) {
    $dataDir = Join-Path $ServerRoot "mpmissions\$mission\storage_1\data"
    if (-not (Test-Path $dataDir)) {
        Write-Host "Skip $mission (no storage_1/data)"
        continue
    }
    $dest = Join-Path $BackupRoot $mission
    New-Item -ItemType Directory -Path $dest -Force | Out-Null

    $shards = Get-ChildItem $dataDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^dynamic_\d+\.(001|002)$' }

    if (-not $shards) {
        Write-Host "$mission : no .001/.002 shards"
        continue
    }

    foreach ($f in $shards) {
        Copy-Item $f.FullName (Join-Path $dest $f.Name) -Force
        Remove-Item $f.FullName -Force
        Write-Host "$mission : removed $($f.Name) (backed up)"
    }
}

# RPT reported File not closed on dynamic_000.001 for Chernarus
$closed = Join-Path $ServerRoot "mpmissions\dayzOffline.chernarusplus\storage_1\data\dynamic_000.001"
if (Test-Path $closed) {
    $dest = Join-Path $BackupRoot "dayzOffline.chernarusplus"
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Copy-Item $closed (Join-Path $dest "dynamic_000.001") -Force
    Remove-Item $closed -Force
    Write-Host "chernarus : removed dynamic_000.001 (backed up)"
}

Write-Host "Backup: $BackupRoot"
