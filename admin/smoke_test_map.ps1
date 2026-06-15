# Start one map, wait for "Player connect enabled", query Steam A2S, then stop it.
param(
    [Parameter(Mandatory = $true)]
    [string]$Map,

    [int]$TimeoutSeconds = 240,

    [string]$QueryHost = '127.0.0.1',

    [string]$ConfigFile,

    [int]$QueryPortOverride = 0,

    [switch]$KeepRunning,

    [switch]$ForceStopExisting
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$LaunchPath = Join-Path $Root 'admin\map_launch.json'
if (-not (Test-Path $LaunchPath)) { throw "Missing $LaunchPath" }

$existing = Get-Process DayZServer_x64 -ErrorAction SilentlyContinue
if ($existing) {
    if (-not $ForceStopExisting) {
        $ids = ($existing | ForEach-Object { $_.Id }) -join ', '
        throw "DayZServer_x64.exe is already running (PID $ids). Stop it first, or rerun with -ForceStopExisting."
    }
    try {
        $existing | Stop-Process -Force
    } catch {
        throw "Could not stop existing DayZServer_x64.exe. Run this from Administrator PowerShell or close DayZServer_x64.exe in Task Manager, then retry. Original error: $_"
    }
    Start-Sleep -Seconds 3
}

$Launch = Get-Content $LaunchPath -Raw | ConvertFrom-Json
$MapCfg = $Launch.maps.$Map
if (-not $MapCfg) {
    $known = ($Launch.maps.PSObject.Properties.Name -join ', ')
    throw "Unknown map: $Map. Known maps: $known"
}

function Get-ValidatedModList {
    param([string]$Raw, [string]$Root, [string[]]$Prepend = @(), [string[]]$Append = @())

    $parts = @()
    foreach ($p in $Prepend) { if ($p) { $parts += $p.Trim() } }
    foreach ($p in ($Raw -split ';')) {
        $m = $p.Trim()
        if ($m) { $parts += $m }
    }
    foreach ($p in $Append) { if ($p) { $parts += $p.Trim() } }

    $seen = @{}
    $ordered = [System.Collections.Generic.List[string]]::new()
    foreach ($m in $parts) {
        if ($seen.ContainsKey($m)) { continue }
        $seen[$m] = $true
        if (-not (Test-Path -LiteralPath (Join-Path $Root $m))) {
            throw "Missing mod folder: $m"
        }
        $ordered.Add($m)
    }
    return ($ordered -join ';')
}

function Format-DayZProcessArguments {
    param([string[]]$ArgumentList)

    $parts = foreach ($a in $ArgumentList) {
        if ($a -match '[\s;]') { '"' + ($a -replace '"', '""') + '"' } else { $a }
    }
    return ($parts -join ' ')
}

$modsFileName = if ($MapCfg.mods_file) { $MapCfg.mods_file } elseif ($Launch.mods_file) { $Launch.mods_file } else { 'chernarus_mods.txt' }
$modsPath = Join-Path $Root (Join-Path 'admin' $modsFileName)
if (-not (Test-Path $modsPath)) { throw "Missing mods file: $modsPath" }

$prepend = @()
if ($MapCfg.prepend_mods) { $prepend = @($MapCfg.prepend_mods) }
$append = @()
if ($MapCfg.extra_mods) { $append = @($MapCfg.extra_mods) }
$mods = Get-ValidatedModList -Raw ((Get-Content $modsPath -Raw).Trim().TrimEnd(';')) -Root $Root -Prepend $prepend -Append $append

$serverMods = $null
if ($MapCfg.server_mods -and $MapCfg.server_mods.Count -gt 0) {
    $valid = @()
    foreach ($s in $MapCfg.server_mods) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $s))) { throw "Missing server mod folder: $s" }
        $valid += $s
    }
    if ($valid.Count -gt 0) { $serverMods = ($valid -join ';') }
}

$exe = Join-Path $Root 'DayZServer_x64.exe'
if (-not (Test-Path $exe)) { throw "Missing $exe" }
$cfgFile = if ($ConfigFile) { $ConfigFile } else { $MapCfg.config }
if (-not (Test-Path (Join-Path $Root $cfgFile))) { throw "Missing config: $cfgFile" }

$port = [int]$MapCfg.port
$queryPort = if ($QueryPortOverride -gt 0) { $QueryPortOverride } else { [int]$MapCfg.steam_query_port }
foreach ($checkPort in @($port, $queryPort, ($port + 2))) {
    if (Get-NetUDPEndpoint -LocalPort $checkPort -ErrorAction SilentlyContinue) {
        throw "UDP port $checkPort is already in use."
    }
}

$profileDir = if ($MapCfg.profiles_dir) { $MapCfg.profiles_dir } else { "profiles_$Map" }
$profileSeed = Join-Path $Root 'admin\ensure_map_profile.ps1'
if (Test-Path $profileSeed) { & $profileSeed -ProfileDir $profileDir }
$profilePath = Join-Path $Root $profileDir
New-Item -ItemType Directory -Force -Path $profilePath | Out-Null
$startTime = Get-Date

$argsList = [System.Collections.Generic.List[string]]::new()
$argsList.Add("-config=$cfgFile")
$argsList.Add("-port=$port")
$argsList.Add("-cpuCount=$($MapCfg.cpu)")
$argsList.Add("-dologs")
$argsList.Add("-adminlog")
$argsList.Add("-netlog")
$argsList.Add("-freezecheck")
$argsList.Add("-filePatching")
if ($MapCfg.bind_ip) { $argsList.Add("-ip=$($MapCfg.bind_ip)") }
$argsList.Add("-mod=$mods")
if ($serverMods) { $argsList.Add("-serverMod=$serverMods") }
$argsList.Add("-profiles=$profileDir")
$argsList.Add("-BEpath=battleye")

Write-Host "Starting $Map on port $port / query $queryPort..."
$process = Start-Process -FilePath $exe -WorkingDirectory $Root -ArgumentList (Format-DayZProcessArguments $argsList.ToArray()) -PassThru
Write-Host "Started PID $($process.Id). Waiting up to $TimeoutSeconds seconds for Player connect enabled..."

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$rpt = $null
$ready = $false
$fatalPatterns = @(
    'termination in:',
    'Cannot create entity',
    'NO VALID SPAWNS'
)

try {
    while ((Get-Date) -lt $deadline) {
        if ($process.HasExited) { throw "Server exited early with code $($process.ExitCode)." }
        $rpt = Get-ChildItem $profilePath -Filter 'DayZServer_x64_*.RPT' -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -ge $startTime.AddSeconds(-5) } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($rpt) {
            $text = Get-Content $rpt.FullName -Raw -ErrorAction SilentlyContinue
            foreach ($pattern in $fatalPatterns) {
                if ($text -match $pattern) {
                    throw "Fatal startup pattern '$pattern' found in $($rpt.Name)."
                }
            }
            if ($text -match 'Player connect enabled') {
                $ready = $true
                break
            }
        }
        Start-Sleep -Seconds 2
    }

    if (-not $ready) { throw "Timed out waiting for Player connect enabled." }
    Write-Host "READY: $Map reached Player connect enabled."

    $queryScript = Join-Path $Root 'admin\query_dayz_server.py'
    & python $queryScript --port $queryPort --host $QueryHost
    if ($LASTEXITCODE -ne 0) { throw "A2S query failed." }
    Write-Host "PASS: $Map booted and answered A2S query."
} finally {
    if (-not $KeepRunning -and -not $process.HasExited) {
        Write-Host "Stopping PID $($process.Id)..."
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        try {
            Wait-Process -Id $process.Id -Timeout 20 -ErrorAction SilentlyContinue
        } catch {
            Start-Sleep -Seconds 3
        }
    } elseif ($KeepRunning) {
        Write-Host "Leaving PID $($process.Id) running because -KeepRunning was set."
    }
}
