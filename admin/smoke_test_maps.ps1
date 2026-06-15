# Run smoke tests for multiple maps and print a compact pass/fail table.
param(
    [string]$Map = 'all-imported',

    [int]$TimeoutSeconds = 300,

    [string]$QueryHost = '127.0.0.1',

    [switch]$ForceStopExisting,

    [switch]$KeepRunningOnLast
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$SmokeScript = Join-Path $Root 'admin\smoke_test_map.ps1'
$LaunchPath = Join-Path $Root 'admin\map_launch.json'
if (-not (Test-Path $SmokeScript)) { throw "Missing $SmokeScript" }
if (-not (Test-Path $LaunchPath)) { throw "Missing $LaunchPath" }

$ImportedMaps = @('deerisle', 'banov', 'esseker', 'rostow', 'iztek', 'alteria')
$Launch = Get-Content $LaunchPath -Raw | ConvertFrom-Json

if ($Map -eq 'all-imported') {
    $Maps = $ImportedMaps
} elseif ($Map -eq 'all') {
    $Maps = @($Launch.maps.PSObject.Properties.Name)
} else {
    $Maps = @($Map)
}

$results = [System.Collections.Generic.List[object]]::new()
for ($i = 0; $i -lt $Maps.Count; $i++) {
    $name = $Maps[$i]
    $cfg = $Launch.maps.$name
    if (-not $cfg) {
        $results.Add([pscustomobject]@{
            Map = $name
            Result = 'FAIL'
            Seconds = 0
            QueryPort = ''
            Server = ''
            Reason = 'Unknown map'
        })
        continue
    }

    Write-Host "`n=== Smoke test: $name ===" -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $args = @(
        '-ExecutionPolicy', 'Bypass',
        '-File', $SmokeScript,
        '-Map', $name,
        '-TimeoutSeconds', $TimeoutSeconds,
        '-QueryHost', $QueryHost
    )
    if ($ForceStopExisting) { $args += '-ForceStopExisting' }
    if ($KeepRunningOnLast -and $i -eq ($Maps.Count - 1)) { $args += '-KeepRunning' }

    $output = & powershell @args 2>&1
    $exitCode = $LASTEXITCODE
    $sw.Stop()
    $output | ForEach-Object { Write-Host $_ }

    $server = ''
    $reason = ''
    foreach ($line in $output) {
        $text = [string]$line
        if ($text -match '^\s+name:\s+(.+)$') { $server = $Matches[1].Trim() }
    }
    if ($exitCode -ne 0) {
        $reason = (($output | Select-Object -Last 8) -join ' ')
        if (-not $reason) { $reason = "Exit code $exitCode" }
    }

    $results.Add([pscustomobject]@{
        Map = $name
        Result = if ($exitCode -eq 0) { 'PASS' } else { 'FAIL' }
        Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
        QueryPort = [int]$cfg.steam_query_port
        Server = $server
        Reason = $reason
    })

    if ($exitCode -ne 0) { break }
    Start-Sleep -Seconds 3
}

Write-Host "`nSmoke test summary:" -ForegroundColor Cyan
$results | Format-Table Map, Result, Seconds, QueryPort, Server, Reason -AutoSize

if (($results | Where-Object { $_.Result -ne 'PASS' }).Count -gt 0) {
    exit 1
}
