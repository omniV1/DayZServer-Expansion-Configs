# Diagnose and repair DayZ Launcher LAN-tab visibility for configured maps.
param(
    [string]$Map = 'all',

    [string]$QueryHost = 'auto',

    [switch]$RepairFirewall,

    [switch]$OpenLauncher,

    [int]$LauncherLogLines = 40
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$LaunchPath = Join-Path $Root 'admin\map_launch.json'
if (-not (Test-Path $LaunchPath)) { throw "Missing $LaunchPath" }

function Get-LanIPv4 {
    $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
        Sort-Object RouteMetric, InterfaceMetric |
        Select-Object -First 1
    if ($route) {
        $ip = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -ne '127.0.0.1' } |
            Select-Object -First 1
        if ($ip) { return $ip.IPAddress }
    }
    return '127.0.0.1'
}

function Get-CfgValue {
    param([string]$Text, [string]$Name)
    $match = [regex]::Match($Text, "(?im)^\s*$([regex]::Escape($Name))\s*=\s*`"?([^`";\r\n]+)")
    if ($match.Success) { return $match.Groups[1].Value.Trim() }
    return ''
}

function Test-A2S {
    param([string]$HostName, [string]$MapName)
    $query = Join-Path $Root 'admin\query_dayz_server.py'
    $output = & python $query --map $MapName --host $HostName --timeout 1.5 2>&1
    if ($LASTEXITCODE -eq 0) {
        $name = ($output | Select-String -Pattern '^\s+name:\s*(.+)$' | Select-Object -First 1).Matches.Groups[1].Value
        return "OK $name"
    }
    return "FAIL $($output -join ' ')"
}

$lanIp = if ($QueryHost -eq 'auto') { Get-LanIPv4 } else { $QueryHost }
$Launch = Get-Content $LaunchPath -Raw | ConvertFrom-Json
$maps = if ($Map -eq 'all') {
    $Launch.maps.PSObject.Properties
} else {
    $cfg = $Launch.maps.$Map
    if (-not $cfg) {
        $known = ($Launch.maps.PSObject.Properties.Name -join ', ')
        throw "Unknown map: $Map. Known maps: $known"
    }
    @([pscustomobject]@{ Name = $Map; Value = $cfg })
}

if ($RepairFirewall) {
    try {
        & (Join-Path $Root 'admin\ensure_dayz_firewall.ps1') -Map $Map
    } catch {
        Write-Warning "Firewall repair failed. Run this from an Administrator PowerShell: $_"
    }
}

$sync = Join-Path $Root 'admin\apply_lan_query_ports.ps1'
if (Test-Path $sync) { & $sync | Out-Null }

$steamRunning = [bool](Get-Process steam -ErrorAction SilentlyContinue)
$launcherRunning = [bool](Get-Process DayZLauncher -ErrorAction SilentlyContinue)
$serverProcesses = @(Get-Process DayZServer_x64 -ErrorAction SilentlyContinue)

Write-Host "LAN Visibility Check"
Write-Host "  LAN IP: $lanIp"
Write-Host "  Steam running: $steamRunning"
Write-Host "  DayZ Launcher running: $launcherRunning"
Write-Host "  DayZ server processes: $($serverProcesses.Count)"
Write-Host ""

foreach ($entry in $maps) {
    $name = $entry.Name
    $cfg = $entry.Value
    $cfgPath = Join-Path $Root $cfg.config
    $cfgText = if (Test-Path $cfgPath) { Get-Content $cfgPath -Raw } else { '' }
    $queryPort = [int]$cfg.steam_query_port
    $gamePort = [int]$cfg.port
    $steamPort = $gamePort + 2
    $endpoint = Get-NetUDPEndpoint -LocalPort $queryPort -ErrorAction SilentlyContinue
    $gameEndpoint = Get-NetUDPEndpoint -LocalPort $gamePort -ErrorAction SilentlyContinue
    $steamEndpoint = Get-NetUDPEndpoint -LocalPort $steamPort -ErrorAction SilentlyContinue
    $cfgQuery = Get-CfgValue -Text $cfgText -Name 'steamQueryPort'
    $cfgSteam = Get-CfgValue -Text $cfgText -Name 'steamPort'

    Write-Host "[$name] $($cfg.title)"
    Write-Host "  game/query/steam: $gamePort / $queryPort / $steamPort"
    Write-Host "  cfg steamQueryPort/steamPort: $cfgQuery / $cfgSteam"
    Write-Host "  UDP endpoints active: game=$([bool]$gameEndpoint) query=$([bool]$endpoint) steam=$([bool]$steamEndpoint)"
    if ($endpoint) {
        Write-Host "  A2S localhost: $(Test-A2S -HostName '127.0.0.1' -MapName $name)"
        if ($lanIp -ne '127.0.0.1') {
            Write-Host "  A2S LAN IP:    $(Test-A2S -HostName $lanIp -MapName $name)"
        }
    } else {
        Write-Host "  A2S: skipped because the query port is not active. Start this map first."
    }
}

$launcherLog = Join-Path $env:LOCALAPPDATA 'DayZ Launcher\Logs\Launcher.log'
if (Test-Path $launcherLog) {
    Write-Host ""
    Write-Host "Recent DayZ Launcher LAN/browser warnings:"
    $patterns = 'Lan|LAN|0\.0\.0\.0:0|Cannot retrieve|server list|failed|error|exception'
    $hits = Select-String -Path $launcherLog -Pattern $patterns -CaseSensitive:$false |
        Select-Object -Last $LauncherLogLines
    if ($hits) {
        foreach ($hit in $hits) {
            $line = ($hit.Line -replace '\s+', ' ').Trim()
            Write-Host "  $line"
        }
    } else {
        Write-Host "  No recent launcher browser warnings found."
    }
}

if (-not $steamRunning) {
    Write-Host ""
    Write-Host "Action needed: start Steam online before opening the DayZ launcher LAN tab."
}

if ($OpenLauncher) {
    $steamRoot = Split-Path $Root -Parent
    $launcher = Join-Path $steamRoot 'steamapps\common\DayZ\DayZLauncher.exe'
    if (Test-Path $launcher) {
        Start-Process -FilePath $launcher | Out-Null
    } else {
        Write-Warning "Could not find DayZLauncher.exe at $launcher"
    }
}

Write-Host ""
Write-Host "LAN tab rule of thumb: start Steam online, start exactly one map, wait for 'Player connect enabled', then refresh LAN."
