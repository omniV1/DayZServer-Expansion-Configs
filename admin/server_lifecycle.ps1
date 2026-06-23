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

function Get-PythonExe {
    foreach ($name in @('python', 'py')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

function Get-RconConfig {
    # Read the map's BattlEye RCon port/password the same way the control center
    # does: the master BEServer_x64.cfg plus any newer active variants BattlEye
    # rewrites once a server boots. Returns $null when RCon is not configured.
    $profileDir = if ($MapCfg.profiles_dir) { [string]$MapCfg.profiles_dir } else { "profiles_$Map" }
    $beFolder = Join-Path $ServerRoot (Join-Path $profileDir 'BattlEye\battleye')
    if (-not (Test-Path $beFolder)) { return $null }

    $candidates = @()
    $master = Join-Path $beFolder 'BEServer_x64.cfg'
    if (Test-Path $master) { $candidates += $master }
    $candidates += Get-ChildItem -Path $beFolder -Filter 'BEServer_x64_active_*.cfg' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | ForEach-Object { $_.FullName }

    foreach ($cfg in $candidates) {
        $text = Get-Content $cfg -Raw -ErrorAction SilentlyContinue
        if (-not $text) { continue }
        $passMatch = [regex]::Match($text, '(?im)^\s*RConPassword\s+(\S+)')
        if (-not $passMatch.Success) { continue }
        $portMatch = [regex]::Match($text, '(?im)^\s*RConPort\s+(\d+)')
        $port = if ($portMatch.Success) { [int]$portMatch.Groups[1].Value } else { $GamePort + 4 }
        return @{ Port = $port; Password = $passMatch.Groups[1].Value }
    }
    return $null
}

function Invoke-GracefulShutdown {
    param([int]$TimeoutSeconds = 30)

    $rcon = Get-RconConfig
    if (-not $rcon) {
        Write-Host "RCon is not configured for $Map; cannot stop cleanly. Enable RCon in the control center so future stops flush persistence instead of force-killing."
        return $false
    }
    $client = Join-Path $PSScriptRoot 'rcon_client.py'
    if (-not (Test-Path $client)) { return $false }
    $python = Get-PythonExe
    if (-not $python) {
        Write-Host "Python was not found on PATH; cannot send RCon #shutdown."
        return $false
    }

    Write-Host "Sending RCon #shutdown to $Map (port $($rcon.Port)) so it can flush persistence ..."
    & $python $client --host 127.0.0.1 --port $rcon.Port --password $rcon.Password --command '#shutdown' --timeout 6 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "RCon #shutdown could not be delivered; will fall back to force-stop."
        return $false
    }

    # A clean shutdown writes the final CE save, so wait for the process to exit
    # on its own rather than killing it mid-write.
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if ((Get-MapServerPids).Count -eq 0) {
            Write-Host "$Map shut down cleanly."
            return $true
        }
    }
    Write-Host "$Map did not exit within $TimeoutSeconds s after #shutdown."
    return $false
}

function Stop-MapServer {
    $pids = Get-MapServerPids
    if ($pids.Count -eq 0) {
        Write-Host "No DayZServer_x64 process is bound to $Map ports ($([string]::Join(', ', $Ports)))."
        return $true
    }
    # Prefer a clean RCon #shutdown: force-killing the process while its periodic
    # [IdleMode] save is mid-write is the classic cause of "Serious stream damage"
    # in storage_*/data/dynamic_*.bin. Force-stop is only the last resort.
    if (Invoke-GracefulShutdown) {
        Write-Host "Stopped $Map."
        return $true
    }
    $pids = Get-MapServerPids
    if ($pids.Count -eq 0) {
        Write-Host "Stopped $Map."
        return $true
    }
    Write-Host "Force-stopping DayZServer_x64 PID(s) for ${Map}: $([string]::Join(', ', $pids))"
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
