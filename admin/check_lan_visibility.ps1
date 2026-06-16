# Diagnose and repair DayZ Launcher LAN-tab visibility for configured maps.
param(
    [string]$Map = 'all',

    [string]$QueryHost = 'auto',

    [switch]$RepairFirewall,

    [switch]$StartMap,

    [switch]$ForceStopExisting,

    [int]$StartupTimeoutSeconds = 240,

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
    param([string]$HostName, [int]$Port)
    $query = Join-Path $Root 'admin\query_dayz_server.py'
    $output = & python $query --port $Port --host $HostName --timeout 1.5 2>&1
    if ($LASTEXITCODE -eq 0) {
        $name = ($output | Select-String -Pattern '^\s+name:\s*(.+)$' | Select-Object -First 1).Matches.Groups[1].Value
        return "OK $name"
    }
    return "FAIL $($output -join ' ')"
}

function Get-MissingLanFirewallRules {
    $required = @(
        'DayZ LAN DayZ Server UDP In',
        'DayZ LAN DayZ Server UDP Out',
        'DayZ LAN Steam UDP In',
        'DayZ LAN Steam UDP Out',
        'DayZ LAN Steam WebHelper UDP In',
        'DayZ LAN Steam WebHelper UDP Out',
        'DayZ LAN DayZ Launcher UDP In',
        'DayZ LAN DayZ Launcher UDP Out',
        'DayZ LAN DayZ Client UDP In',
        'DayZ LAN DayZ Client UDP Out'
    )
    $missing = @()
    foreach ($name in $required) {
        $rule = Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
        if (-not $rule -or $rule.Enabled -ne 'True' -or $rule.Action -ne 'Allow') {
            $missing += $name
        }
    }
    return $missing
}

function Get-LanScanQueryPort {
    param([int]$ConfiguredPort)
    $scanPorts = @(27016, 27017, 27018, 27019, 27020, 27015)
    if ($ConfiguredPort -in $scanPorts) { return $ConfiguredPort }
    foreach ($candidate in $scanPorts) {
        if (-not (Get-NetUDPEndpoint -LocalPort $candidate -ErrorAction SilentlyContinue)) {
            return $candidate
        }
    }
    return $ConfiguredPort
}

function Test-LanScanQueryPort {
    param([int]$Port)
    return $Port -in @(27016, 27017, 27018, 27019, 27020, 27015)
}

function New-LanQueryConfig {
    param(
        [string]$SourceConfig,
        [string]$MapName,
        [int]$LanQueryPort
    )
    $runtimeDir = Join-Path $Root 'local_runtime\lan_query'
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    $runtimeName = "serverDZ_$MapName.lan.cfg"
    $runtimePath = Join-Path $runtimeDir $runtimeName
    $text = Get-Content (Join-Path $Root $SourceConfig) -Raw
    if ($text -match 'steamQueryPort\s*=') {
        $text = $text -replace 'steamQueryPort\s*=\s*\d+\s*;', "steamQueryPort = $LanQueryPort;"
    } else {
        $text = $text -replace '(instanceId\s*=\s*\d+\s*;)', "`$1`nsteamQueryPort = $LanQueryPort;"
    }
    Set-Content -Path $runtimePath -Value $text -Encoding UTF8
    return (Join-Path 'local_runtime\lan_query' $runtimeName)
}

$lanIp = if ($QueryHost -eq 'auto') { Get-LanIPv4 } else { $QueryHost }
$Launch = Get-Content $LaunchPath -Raw | ConvertFrom-Json
$maps = if ($Map -eq 'all') {
    if ($StartMap) { throw "-StartMap requires one map name, not -Map all." }
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

if ($StartMap) {
    $smoke = Join-Path $Root 'admin\smoke_test_map.ps1'
    if (-not (Test-Path $smoke)) { throw "Missing $smoke" }
    $startCfg = $Launch.maps.$Map
    $startQueryPort = [int]$startCfg.steam_query_port
    $startConfigFile = $startCfg.config
    $lanQueryPort = Get-LanScanQueryPort -ConfiguredPort $startQueryPort
    if ($lanQueryPort -ne $startQueryPort) {
        $startConfigFile = New-LanQueryConfig -SourceConfig $startConfigFile -MapName $Map -LanQueryPort $lanQueryPort
        $startQueryPort = $lanQueryPort
        Write-Host "LAN query auto: using temporary $startConfigFile with steamQueryPort $startQueryPort so the launcher LAN scan can find $Map."
    }
    $args = @{
        Map = $Map
        TimeoutSeconds = $StartupTimeoutSeconds
        QueryHost = if ($QueryHost -eq 'auto') { '127.0.0.1' } else { $QueryHost }
        KeepRunning = $true
        ConfigFile = $startConfigFile
        QueryPortOverride = $startQueryPort
    }
    if ($ForceStopExisting) { $args.ForceStopExisting = $true }
    & $smoke @args
    if ($LASTEXITCODE -ne 0) { throw "Failed to start and validate $Map." }
    Start-Sleep -Seconds 2
}

$steamRunning = [bool](Get-Process steam -ErrorAction SilentlyContinue)
$launcherRunning = [bool](Get-Process DayZLauncher -ErrorAction SilentlyContinue)
$serverProcesses = @(Get-Process DayZServer_x64 -ErrorAction SilentlyContinue)
$missingFirewallRules = @(Get-MissingLanFirewallRules)

Write-Host "LAN Visibility Check"
Write-Host "  LAN IP: $lanIp"
Write-Host "  Steam running: $steamRunning"
Write-Host "  DayZ Launcher running: $launcherRunning"
Write-Host "  DayZ server processes: $($serverProcesses.Count)"
Write-Host "  LAN firewall program rules missing: $($missingFirewallRules.Count)"
if ($missingFirewallRules.Count -gt 0) {
    Write-Host "  Run from Administrator PowerShell: powershell -ExecutionPolicy Bypass -File admin\check_lan_visibility.ps1 -Map $Map -RepairFirewall"
}
if ($serverProcesses.Count -eq 0) {
    Write-Host "  No server is running, so LAN cannot list any of these maps yet."
    if ($Map -ne 'all') {
        Write-Host "  Start and check this map with: powershell -ExecutionPolicy Bypass -File admin\check_lan_visibility.ps1 -Map $Map -StartMap"
    }
}
Write-Host ""

foreach ($entry in $maps) {
    $name = $entry.Name
    $cfg = $entry.Value
    $gamePort = [int]$cfg.port
    $steamPort = $gamePort + 2
    $cfgPath = Join-Path $Root $cfg.config
    $runtimeCfgPath = Join-Path $Root (Join-Path 'local_runtime\lan_query' "serverDZ_$name.lan.cfg")
    $useRuntimeCfg = $false
    $runtimeCfgText = ''
    if (Test-Path $runtimeCfgPath) {
        $runtimeCfgText = Get-Content $runtimeCfgPath -Raw
        $runtimeQuery = Get-CfgValue -Text $runtimeCfgText -Name 'steamQueryPort'
        $runtimeEndpoint = if ($runtimeQuery) { Get-NetUDPEndpoint -LocalPort ([int]$runtimeQuery) -ErrorAction SilentlyContinue } else { $null }
        $runtimeGameEndpoint = Get-NetUDPEndpoint -LocalPort $gamePort -ErrorAction SilentlyContinue
        $useRuntimeCfg = ($StartMap -and $name -eq $Map) -or ($runtimeEndpoint -and $runtimeGameEndpoint)
    }
    if ($useRuntimeCfg) { $cfgPath = $runtimeCfgPath }
    $cfgText = if (Test-Path $cfgPath) { Get-Content $cfgPath -Raw } else { '' }
    $queryPort = if ($useRuntimeCfg) { [int](Get-CfgValue -Text $cfgText -Name 'steamQueryPort') } else { [int]$cfg.steam_query_port }
    $endpoint = Get-NetUDPEndpoint -LocalPort $queryPort -ErrorAction SilentlyContinue
    $gameEndpoint = Get-NetUDPEndpoint -LocalPort $gamePort -ErrorAction SilentlyContinue
    $steamEndpoint = Get-NetUDPEndpoint -LocalPort $steamPort -ErrorAction SilentlyContinue
    $cfgQuery = Get-CfgValue -Text $cfgText -Name 'steamQueryPort'
    $cfgSteam = Get-CfgValue -Text $cfgText -Name 'steamPort'

    Write-Host "[$name] $($cfg.title)"
    Write-Host "  game/query/steam: $gamePort / $queryPort / $steamPort"
    Write-Host "  cfg steamQueryPort/steamPort: $cfgQuery / $cfgSteam"
    if ($useRuntimeCfg) {
        Write-Host "  LAN runtime cfg active: local_runtime\lan_query\serverDZ_$name.lan.cfg"
    }
    Write-Host "  UDP endpoints active: game=$([bool]$gameEndpoint) query=$([bool]$endpoint) steam=$([bool]$steamEndpoint)"
    if ($endpoint -and -not (Test-LanScanQueryPort -Port $queryPort)) {
        Write-Warning "$name is answering A2S on $queryPort, but Steam/DayZ LAN auto-discovery may not scan that port. Restart with: powershell -ExecutionPolicy Bypass -File admin\check_lan_visibility.ps1 -Map $name -StartMap -ForceStopExisting"
    }
    if ($endpoint) {
        Write-Host "  A2S localhost: $(Test-A2S -HostName '127.0.0.1' -Port $queryPort)"
        if ($lanIp -ne '127.0.0.1') {
            Write-Host "  A2S LAN IP:    $(Test-A2S -HostName $lanIp -Port $queryPort)"
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
    $commonRoot = Split-Path $Root -Parent
    $launcher = Join-Path $commonRoot 'DayZ\DayZLauncher.exe'
    if (Test-Path $launcher) {
        Start-Process -FilePath $launcher | Out-Null
    } else {
        Write-Warning "Could not find DayZLauncher.exe at $launcher"
    }
}

Write-Host ""
Write-Host "LAN tab rule of thumb: start Steam online, start exactly one map, wait for 'Player connect enabled', then refresh LAN."
Write-Host "If A2S is OK but LAN is still empty, run: powershell -ExecutionPolicy Bypass -File admin\reset_dayz_launcher_browser.ps1 -StopLauncher -OpenLauncher"
