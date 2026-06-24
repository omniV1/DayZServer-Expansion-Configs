# Launch-DayZMap.ps1 - start a map with the shared Chernarus mod list (admin/map_launch.json + admin/chernarus_mods.txt)
# Usage: .\Launch-DayZMap.ps1 -Map enoch
#        .\Launch-DayZMap.ps1 -Map namalsk
#        .\Launch-DayZMap.ps1 -Map takistan
#        .\Launch-DayZMap.ps1 -Map chernarus -ScheduledRestartSeconds 14390
#
# Mod list is passed as a single quoted "-mod=..." argument (required for @Dabs Framework etc.).
# Each map gets its own game port and steamQueryPort so the launcher can read the mod list.

param(
    [Parameter(Mandatory = $true)]
    [string]$Map,

    [int]$ScheduledRestartSeconds = 0,

    [switch]$DisableLanQueryAuto
)

$ErrorActionPreference = 'Stop'
$ServerRoot = $PSScriptRoot
$MapCfgPath = Join-Path $ServerRoot 'admin\map_launch.json'
if (-not (Test-Path $MapCfgPath)) { throw "Missing $MapCfgPath" }

$lanPatch = Join-Path $ServerRoot 'admin\apply_lan_query_ports.ps1'
if (Test-Path $lanPatch) { & $lanPatch }

$Launch = Get-Content $MapCfgPath -Raw | ConvertFrom-Json
$MapNames = @($Launch.maps.PSObject.Properties.Name)
$MapCfg = $Launch.maps.$Map
if (-not $MapCfg) { throw "Unknown map in map_launch.json: $Map. Known maps: $($MapNames -join ', ')" }

$modsFileName = if ($MapCfg.mods_file) { $MapCfg.mods_file } else { 'chernarus_mods.txt' }
$ModsFile = Join-Path $ServerRoot (Join-Path 'admin' $modsFileName)
if (-not (Test-Path $ModsFile)) { throw "Missing $ModsFile" }

$profileDir = if ($MapCfg.profiles_dir) { $MapCfg.profiles_dir } else { "profiles_$Map" }
$profileSeed = Join-Path $ServerRoot 'admin\ensure_map_profile.ps1'
if (Test-Path $profileSeed) { & $profileSeed -ProfileDir $profileDir }

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
        $dir = Join-Path $Root $m
        if (-not (Test-Path -LiteralPath $dir)) {
            Write-Warning "Mod folder missing (skipped): $m"
            continue
        }
        $ordered.Add($m)
    }
    return ($ordered -join ';')
}

$BaseRaw = (Get-Content $ModsFile -Raw).Trim().TrimEnd(';')
$Prepend = @()
if ($MapCfg.prepend_mods) { $Prepend = @($MapCfg.prepend_mods) }
$Append = @()
if ($MapCfg.extra_mods) { $Append = @($MapCfg.extra_mods) }

$Mods = Get-ValidatedModList -Raw $BaseRaw -Root $ServerRoot -Prepend $Prepend -Append $Append
if (-not $Mods) {
    throw "No valid mod folders found. Check admin/chernarus_mods.txt and @folders under $ServerRoot"
}

$ServerModArg = $null
if ($MapCfg.server_mods -and $MapCfg.server_mods.Count -gt 0) {
    $sm = @()
    foreach ($s in $MapCfg.server_mods) {
        if (Test-Path -LiteralPath (Join-Path $ServerRoot $s)) { $sm += $s }
        else { Write-Warning "Server mod folder missing (skipped): $s" }
    }
    if ($sm.Count -gt 0) { $ServerModArg = ($sm -join ';') }
}

$Exe = Join-Path $ServerRoot 'DayZServer_x64.exe'
if (-not (Test-Path $Exe)) { throw "Missing $Exe" }

$CfgFile = $MapCfg.config
if (-not (Test-Path (Join-Path $ServerRoot $CfgFile))) { throw "Missing config: $CfgFile" }

$Port = [int]$MapCfg.port
$QueryPort = if ($MapCfg.steam_query_port) { [int]$MapCfg.steam_query_port } else { $Port + 1 }
$ConfiguredQueryPort = $QueryPort

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

function New-LanQueryConfig {
    param(
        [string]$SourceConfig,
        [string]$MapName,
        [int]$LanQueryPort
    )

    $runtimeDir = Join-Path $ServerRoot 'local_runtime\lan_query'
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    $runtimeName = "serverDZ_$MapName.lan.cfg"
    $runtimePath = Join-Path $runtimeDir $runtimeName
    $text = Get-Content (Join-Path $ServerRoot $SourceConfig) -Raw
    if ($text -match 'steamQueryPort\s*=') {
        $text = $text -replace 'steamQueryPort\s*=\s*\d+\s*;', "steamQueryPort = $LanQueryPort;"
    } else {
        $text = $text -replace '(instanceId\s*=\s*\d+\s*;)', "`$1`nsteamQueryPort = $LanQueryPort;"
    }
    Set-Content -Path $runtimePath -Value $text -Encoding UTF8
    return (Join-Path 'local_runtime\lan_query' $runtimeName)
}

if (-not $DisableLanQueryAuto) {
    $lanQueryPort = Get-LanScanQueryPort -ConfiguredPort $QueryPort
    if ($lanQueryPort -ne $QueryPort) {
        $CfgFile = New-LanQueryConfig -SourceConfig $CfgFile -MapName $Map -LanQueryPort $lanQueryPort
        $QueryPort = $lanQueryPort
        Write-Host "LAN query auto: using temporary $CfgFile with steamQueryPort $QueryPort instead of configured $ConfiguredQueryPort."
    }
}

foreach ($checkPort in @($Port, $QueryPort, ($Port + 2))) {
    if (Get-NetUDPEndpoint -LocalPort $checkPort -ErrorAction SilentlyContinue) {
        throw "UDP port $checkPort is already in use. Stop every DayZServer_x64.exe, then start maps in order (Chernarus -> Livonia -> Namalsk -> Sakhal -> Takistan)."
    }
}

Write-Host "Map: $($MapCfg.title)"
Write-Host "Config: $CfgFile | port $Port | steamQueryPort $QueryPort"
if ($QueryPort -notin @(27015, 27016, 27017, 27018, 27019, 27020)) {
    Write-Warning "steamQueryPort $QueryPort may not be scanned by the Steam/DayZ LAN browser. Free one of 27016-27020 or use the temporary LAN query config path."
}
Write-Host "Profiles: $profileDir"
Write-Host "LAN: start Steam first, then this server, then DayZ launcher -> Servers -> LAN tab (query $QueryPort)."
Write-Host "LAN check: powershell -ExecutionPolicy Bypass -File admin\check_lan_visibility.ps1 -Map $Map -RepairFirewall"
Write-Host "Mods: $($Mods.Length) chars, $($Mods.Split(';').Count) folders"
if ($ServerModArg) { Write-Host "Server mods: $ServerModArg" }

function New-DayZArgumentList {
    param([bool]$IncludeProfiles = $true)

    $list = [System.Collections.Generic.List[string]]::new()
    $list.Add("-config=$CfgFile")
    $list.Add("-port=$Port")
    $list.Add("-cpuCount=$($MapCfg.cpu)")
    $list.Add("-dologs")
    $list.Add("-adminlog")
    $list.Add("-netlog")
    $list.Add("-freezecheck")
    # -filePatching loads loose/unpacked files over PBOs and relaxes mod
    # verification -- a dev-only flag that causes clients to be kicked with
    # "client has a PBO which is not part of the server" even when files match.
    # Off by default; opt in per map with "file_patching": true for mod dev.
    if ($MapCfg.file_patching) { $list.Add("-filePatching") }
    # Do not use -ip=127.0.0.1: that binds loopback only and hides the server from the LAN tab.
    if ($MapCfg.bind_ip) {
        $list.Add("-ip=$($MapCfg.bind_ip)")
    }
    $list.Add("-mod=$Mods")
    if ($ServerModArg) { $list.Add("-serverMod=$ServerModArg") }
    if ($IncludeProfiles) {
        $list.Add("-profiles=$profileDir")
        $list.Add("-BEpath=battleye")
    }
    return $list.ToArray()
}

# Start-Process -ArgumentList with a string[] splits -mod= at spaces (@Dabs Framework).
# Build one quoted command line so the full mod chain loads (same as start_Takistan_DIRECT.cmd).
function Format-DayZProcessArguments {
    param([string[]]$ArgumentList)

    $parts = foreach ($a in $ArgumentList) {
        if ($a -match '[\s;]') { '"' + ($a -replace '"', '""') + '"' } else { $a }
    }
    return ($parts -join ' ')
}

if ($ScheduledRestartSeconds -gt 0) {
    Write-Host "Scheduled restart every $ScheduledRestartSeconds seconds."
    while ($true) {
        $procArgs = New-DayZArgumentList -IncludeProfiles $true
        $argLine = Format-DayZProcessArguments -ArgumentList $procArgs
        $p = Start-Process -FilePath $Exe -WorkingDirectory $ServerRoot -ArgumentList $argLine -PassThru
        Write-Host "Started PID $($p.Id). Waiting $ScheduledRestartSeconds s..."
        Start-Sleep -Seconds $ScheduledRestartSeconds
        if (-not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 5
        }
    }
}

$argList = New-DayZArgumentList -IncludeProfiles $true
$argLine = Format-DayZProcessArguments -ArgumentList $argList
Write-Host 'Starting DayZServer_x64.exe ...'
$p = Start-Process -FilePath $Exe -WorkingDirectory $ServerRoot -ArgumentList $argLine -Wait -PassThru
exit $p.ExitCode
