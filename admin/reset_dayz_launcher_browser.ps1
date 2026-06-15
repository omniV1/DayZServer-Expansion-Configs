# Back up and reset DayZ Launcher's server-browser cache/state.
param(
    [switch]$StopLauncher,

    [switch]$OpenLauncher
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$LauncherDir = Join-Path $env:LOCALAPPDATA 'DayZ Launcher'
if (-not (Test-Path $LauncherDir)) {
    throw "DayZ Launcher local data folder not found: $LauncherDir"
}

$launcherProcesses = @(Get-Process DayZLauncher -ErrorAction SilentlyContinue)
if ($launcherProcesses.Count -gt 0) {
    if (-not $StopLauncher) {
        throw "DayZLauncher.exe is running. Close it first, or rerun with -StopLauncher."
    }
    $launcherProcesses | Stop-Process -Force
    Start-Sleep -Seconds 2
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $Root 'local_backups\dayz_launcher'
$backupDir = Join-Path $backupRoot $stamp
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$files = @(
    'ServerBrowser.Settings.json',
    'Servers.json',
    'Servers.Banned.json',
    'Servers.Monetized.json',
    'Servers.Official.json',
    'Steam.json',
    'FavouriteServers.xml'
)

foreach ($file in $files) {
    $path = Join-Path $LauncherDir $file
    if (Test-Path $path) {
        Copy-Item -LiteralPath $path -Destination (Join-Path $backupDir $file) -Force
    }
}

$settingsPath = Join-Path $LauncherDir 'ServerBrowser.Settings.json'
$settings = @{
    community = @{ filters = @(''); sort = 'None'; sort_reversed = $false }
    favorites = @{ filters = @(''); sort = 'None'; sort_reversed = $false }
    friends = @{ filters = @(''); sort = 'None'; sort_reversed = $false }
    lan = @{ filters = @(''); sort = 'ServerName'; sort_reversed = $false }
    official = @{ filters = @(''); sort = 'None'; sort_reversed = $false }
    recent = @{ filters = @(''); sort = 'None'; sort_reversed = $false }
}
$json = $settings | ConvertTo-Json -Compress -Depth 5
$json = $json -replace 'sort_reversed', 'sort-reversed'
Set-Content -Path $settingsPath -Value $json -Encoding UTF8

foreach ($file in @('Servers.json', 'Servers.Banned.json', 'Servers.Monetized.json', 'Servers.Official.json', 'Steam.json')) {
    $path = Join-Path $LauncherDir $file
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

$favorites = Join-Path $Root 'admin\install_launcher_favorites.ps1'
if (Test-Path $favorites) {
    & $favorites
}

Write-Host "Backed up launcher browser files to $backupDir"
Write-Host "Reset DayZ Launcher server-browser cache/settings."
Write-Host "Start Steam online, start one DayZ server, then open DayZ Launcher -> Servers -> LAN."

if ($OpenLauncher) {
    $commonRoot = Split-Path $Root -Parent
    $launcher = Join-Path $commonRoot 'DayZ\DayZLauncher.exe'
    if (Test-Path $launcher) {
        Start-Process -FilePath $launcher | Out-Null
    } else {
        Write-Warning "Could not find DayZLauncher.exe at $launcher"
    }
}
