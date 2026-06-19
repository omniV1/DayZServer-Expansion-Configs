# server_lifecycle.ps1 - guarded start/stop/restart for one map.
#
# Wraps the existing Launch-DayZMap.ps1 (no arbitrary commands). Start spawns the
# launcher in a detached console and returns immediately. Stop only stops
# DayZServer_x64 processes that are bound to the selected map's UDP ports, so it
# never touches other applications.
#
# Usage:
#   server_lifecycle.ps1 -Action status  -Map enoch
#   server_lifecycle.ps1 -Action start   -Map enoch
#   server_lifecycle.ps1 -Action stop    -Map enoch
#   server_lifecycle.ps1 -Action restart -Map enoch
#   server_lifecycle.ps1 -Action start   -Map enoch -DryRun

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [string]$Map,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ServerRoot = Split-Path $PSScriptRoot -Parent
$MapCfgPath = Join-Path $ServerRoot 'admin\map_launch.json'
if (-not (Test-Path $MapCfgPath)) { throw "Missing $MapCfgPath" }

$Launch = Get-Content $MapCfgPath -Raw | ConvertFrom-Json
$MapNames = @($Launch.maps.PSObject.Properties.Name)
$MapCfg = $Launch.maps.$Map
if (-not $MapCfg) { throw "Unknown map: $Map. Known maps: $($MapNames -join ', ')" }

$GamePort = [int]$MapCfg.port
$QueryPort = if ($MapCfg.steam_query_port) { [int]$MapCfg.steam_query_port } else { $GamePort + 1 }
$SteamPort = $GamePort + 2
$Ports = @($GamePort, $QueryPort, $SteamPort)

function Get-MapServerPids {
    $pids = @{}
    # Primary: match DayZServer_x64 by its '-port=<gamePort>' command line. This works
    # the instant the process starts, before UDP ports are bound, and is unaffected by
    # the LAN query-port remap (only the query port changes; -port stays the game port).
    $procs = Get-CimInstance Win32_Process -Filter "Name='DayZServer_x64.exe'" -ErrorAction SilentlyContinue
    foreach ($proc in $procs) {
        $cmd = $proc.CommandLine
        if ($cmd -and ($cmd -match "-port=$GamePort(\s|$)")) {
            $pids[[int]$proc.ProcessId] = $true
        }
    }
    # Fallback: any DayZServer_x64 already bound to this map's UDP ports.
    foreach ($port in $Ports) {
        $endpoints = Get-NetUDPEndpoint -LocalPort $port -ErrorAction SilentlyContinue
        foreach ($ep in $endpoints) {
            $owning = $ep.OwningProcess
            if (-not $owning) { continue }
            $proc = Get-Process -Id $owning -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -eq 'DayZServer_x64') {
                $pids[[int]$owning] = $true
            }
        }
    }
    return @($pids.Keys)
}

function Show-Status {
    $pids = Get-MapServerPids
    Write-Host "Map: $($MapCfg.title) ($Map)"
    Write-Host "Ports: game $GamePort, query $QueryPort, steam $SteamPort"
    if ($pids.Count -gt 0) {
        Write-Host "Running: yes (DayZServer_x64 PID(s) $([string]::Join(', ', $pids)))"
    }
    else {
        Write-Host 'Running: no'
    }
    return $pids
}

function Stop-MapServer {
    $pids = Get-MapServerPids
    if ($pids.Count -eq 0) {
        Write-Host "No DayZServer_x64 process is bound to $Map ports ($([string]::Join(', ', $Ports)))."
        return $true
    }
    Write-Host "Stopping DayZServer_x64 PID(s) for ${Map}: $([string]::Join(', ', $pids))"
    foreach ($procId in $pids) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 3
    $still = Get-MapServerPids
    if ($still.Count -gt 0) {
        throw "Failed to stop PID(s): $([string]::Join(', ', $still)). Try again or stop them in Task Manager."
    }
    Write-Host "Stopped $Map."
    return $true
}

function Start-MapServer {
    $running = Get-MapServerPids
    if ($running.Count -gt 0) {
        Write-Host "$Map is already running (PID(s) $([string]::Join(', ', $running))). Use restart to cycle it."
        return $true
    }
    $launchScript = Join-Path $ServerRoot 'Launch-DayZMap.ps1'
    if (-not (Test-Path $launchScript)) { throw "Missing $launchScript" }
    $psArgs = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', "`"$launchScript`"",
        '-Map', $Map
    )
    if ($DryRun) {
        Write-Host "[DryRun] Would launch: powershell.exe $([string]::Join(' ', $psArgs))"
        Write-Host "[DryRun] Working directory: $ServerRoot"
        return $true
    }
    Write-Host "Starting $Map in a new console via Launch-DayZMap.ps1 ..."
    $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $psArgs -WorkingDirectory $ServerRoot -PassThru
    Write-Host "Launcher started (console PID $($proc.Id)). The server boots in that window."
    Write-Host "Watch the Dashboard: game port $GamePort and query port $QueryPort go active once it is up."
    return $true
}

switch ($Action) {
    'status' { Show-Status | Out-Null }
    'stop' { Stop-MapServer | Out-Null }
    'start' { Start-MapServer | Out-Null }
    'restart' {
        Write-Host "Restarting $Map ..."
        Stop-MapServer | Out-Null
        Start-Sleep -Seconds 2
        Start-MapServer | Out-Null
    }
}

exit 0
