# Create per-map profile folder (logs, Expansion, BE) so instances do not fight over profiles/.
param(
    [Parameter(Mandatory = $true)]
    [string]$ProfileDir
)

$ErrorActionPreference = 'Stop'
$ServerRoot = Split-Path $PSScriptRoot -Parent
$dest = Join-Path $ServerRoot $ProfileDir
if (Test-Path $dest) { return }

$src = Join-Path $ServerRoot 'profiles'
if (-not (Test-Path $src)) {
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Write-Host "Created empty profile dir: $ProfileDir"
    return
}

New-Item -ItemType Directory -Path $dest -Force | Out-Null
$copyDirs = @(
    'Users',
    'ExpansionMod\Settings',
    'CodeLock',
    'PermissionsFramework',
    'configs',
    'CommunityOnlineTools',
    'VPPAdminTools',
    'AIWarZones'
)
foreach ($rel in $copyDirs) {
    $from = Join-Path $src $rel
    if (-not (Test-Path $from)) { continue }
    $to = Join-Path $dest $rel
    New-Item -ItemType Directory -Path (Split-Path $to -Parent) -Force -ErrorAction SilentlyContinue | Out-Null
    robocopy $from $to /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) { Write-Warning "robocopy issue seeding $rel -> $ProfileDir (code $LASTEXITCODE)" }
}
Write-Host "Seeded $ProfileDir from profiles (mod settings only, no RPT/logs)."
