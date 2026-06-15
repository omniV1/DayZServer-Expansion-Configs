# Add Windows Firewall rules for the configured DayZ game and Steam query UDP ports.
param(
    [string]$Map = 'all'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$LaunchPath = Join-Path $Root 'admin\map_launch.json'
if (-not (Test-Path $LaunchPath)) { throw "Missing $LaunchPath" }

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

$ports = [System.Collections.Generic.SortedSet[int]]::new()
foreach ($entry in $maps) {
    $cfg = $entry.Value
    [void]$ports.Add([int]$cfg.port)
    [void]$ports.Add([int]$cfg.steam_query_port)
    [void]$ports.Add(([int]$cfg.port + 2))
}

foreach ($port in @($ports)) {
    $ruleName = "DayZ Server UDP $port"
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($existing) {
        Set-NetFirewallRule -DisplayName $ruleName -Enabled True -Direction Inbound -Action Allow
        Set-NetFirewallPortFilter -AssociatedNetFirewallRule $existing -Protocol UDP -LocalPort $port
        Write-Host "Updated firewall rule: $ruleName"
    } else {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol UDP -LocalPort $port | Out-Null
        Write-Host "Created firewall rule: $ruleName"
    }
}

Write-Host "Launcher visibility still requires the server to reach 'Player connect enabled' in its RPT log."
