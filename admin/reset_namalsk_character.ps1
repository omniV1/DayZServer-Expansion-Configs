# Wipes Namalsk character + Expansion quest/ATM data (fixes LEHS kicks and corrupt reputation/XP).
# Stop the Namalsk server first.

$ErrorActionPreference = 'Stop'
$root = 'c:\Games\Steam\steamapps\common\DayZServer'
$profile = Join-Path $root 'profiles_namalsk'
$storage = Join-Path $root 'mpmissions\regular.namalsk\storage_3\data'
$players = Join-Path (Split-Path $storage -Parent) 'players'

$wipeDirs = @($storage, $players)
$wipeFiles = @(
    (Join-Path $profile 'ExpansionMod\Quests\PlayerData\*'),
    (Join-Path $profile 'ExpansionMod\ATM\*'),
    (Join-Path $profile 'ExpansionMod\Hardline\PlayerData\*')
)

$removed = $false
foreach ($dir in $wipeDirs) {
    if (-not (Test-Path $dir)) { continue }
    $bak = "$dir.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $dir $bak -Recurse -Force
    Write-Host "Backup: $bak"
    Remove-Item $dir -Recurse -Force
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $removed = $true
}

foreach ($pattern in $wipeFiles) {
    $parent = Split-Path $pattern -Parent
    if (-not (Test-Path $parent)) { continue }
    Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | ForEach-Object {
        $bak = "$($_.FullName).backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Copy-Item $_.FullName $bak -Force
        Remove-Item $_.FullName -Force
        Write-Host "Removed: $($_.Name)"
        $removed = $true
    }
}

if ($removed) {
    Write-Host 'Namalsk player data reset. Restart server, use Owens-Namalsk preset, then join.'
} else {
    Write-Host 'Nothing found to reset.'
}
