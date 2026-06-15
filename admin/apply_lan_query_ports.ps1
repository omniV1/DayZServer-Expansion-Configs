# Sync steamQueryPort / steamPort in each serverDZ*.cfg from admin/map_launch.json.
# LAN tab: Steam query ports come from admin/map_launch.json (27016+ for multi-instance).

$ErrorActionPreference = 'Stop'
$ServerRoot = Split-Path $PSScriptRoot -Parent
$launchPath = Join-Path $PSScriptRoot 'map_launch.json'
if (-not (Test-Path $launchPath)) { exit 1 }

$launch = Get-Content $launchPath -Raw | ConvertFrom-Json

foreach ($prop in $launch.maps.PSObject.Properties) {
    $mapKey = $prop.Name
    $m = $prop.Value
    $cfgPath = Join-Path $ServerRoot $m.config
    if (-not (Test-Path $cfgPath)) {
        Write-Warning "Missing config for ${mapKey}: $($m.config)"
        continue
    }

    $queryPort = if ($null -ne $m.steam_query_port) { [int]$m.steam_query_port } else { 27016 }
    $steamPort = [int]$m.port + 2
    $text = Get-Content $cfgPath -Raw
    $orig = $text

    if ($text -match 'steamQueryPort\s*=') {
        $text = $text -replace 'steamQueryPort\s*=\s*\d+\s*;[^\r\n]*', "steamQueryPort = $queryPort;"
    } else {
        $text = $text -replace '(instanceId\s*=\s*\d+\s*;)', "`$1`nsteamQueryPort = $queryPort;"
    }

    if ($text -match 'steamPort\s*=') {
        $text = $text -replace 'steamPort\s*=\s*\d+\s*;[^\r\n]*', "steamPort = $steamPort;"
    } else {
        $text = $text -replace "(steamQueryPort\s*=\s*$queryPort\s*;)", "`$1`nsteamPort = $steamPort;"
    }

    if ($text -ne $orig) {
        Set-Content -Path $cfgPath -Value $text.TrimEnd() -NoNewline
        Add-Content -Path $cfgPath -Value "`n"
        Write-Host "LAN query: $($m.config) -> steamQueryPort $queryPort, steamPort $steamPort"
    }
}
