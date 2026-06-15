# Legacy wrapper. Prefer ensure_dayz_firewall.ps1, which reads admin/map_launch.json
# and covers every current map/query port.
param(
    [string]$Map = 'all'
)

$ErrorActionPreference = 'Stop'
$Current = Join-Path $PSScriptRoot 'ensure_dayz_firewall.ps1'
if (-not (Test-Path $Current)) { throw "Missing $Current" }

Write-Warning "ensure_firewall_dayz.ps1 is legacy; forwarding to ensure_dayz_firewall.ps1."
& $Current -Map $Map
