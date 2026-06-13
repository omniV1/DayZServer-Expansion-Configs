# Takistan — use unified launcher (full Chernarus mod list + @TakistanPlus after @Dabs Framework).
param(
    [switch]$AutoRestart,
    [int]$ScheduledRestartSeconds = 0
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$launcher = Join-Path $here 'Launch-DayZMap.ps1'
if (-not (Test-Path $launcher)) { throw "Missing $launcher" }

if ($ScheduledRestartSeconds -gt 0) {
    & $launcher -Map takistan -ScheduledRestartSeconds $ScheduledRestartSeconds
    exit $LASTEXITCODE
}

if ($AutoRestart) {
    while ($true) {
        & $launcher -Map takistan
        Write-Host 'AutoRestart: waiting 60s...'
        Start-Sleep -Seconds 60
    }
}

& $launcher -Map takistan
exit $LASTEXITCODE
