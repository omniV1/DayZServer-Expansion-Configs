# Writes DayZ Launcher favorites for all Owen maps (REMOTE tab). LAN tab is unreliable for multi-instance.
$ErrorActionPreference = 'Stop'
$launchPath = Join-Path $PSScriptRoot 'map_launch.json'
$launch = Get-Content $launchPath -Raw | ConvertFrom-Json
$favPath = Join-Path $env:LOCALAPPDATA 'DayZ Launcher\FavouriteServers.xml'

function ConvertTo-IpInt {
    param([string]$Ip)
    $p = $Ip.Split('.')
    if ($p.Count -ne 4) { throw "Bad IP: $Ip" }
    return [int]$p[0] + ([int]$p[1] -shl 8) + ([int]$p[2] -shl 16) + ([int]$p[3] -shl 24)
}

$entries = New-Object System.Collections.Generic.List[string]
foreach ($prop in $launch.maps.PSObject.Properties) {
    $m = $prop.Value
    $gamePort = [int]$m.port
    $queryPort = [int]$m.steam_query_port
    $name = $m.title
    foreach ($hostIp in @('127.0.0.1', '192.168.0.3')) {
        $ipInt = ConvertTo-IpInt $hostIp
        $q = "${hostIp}:$queryPort"
        $c = "${hostIp}:$gamePort"
        $entries.Add(
            "    <Server IpAddress=`"$ipInt`" Port=`"$gamePort`" QueryEndPoint=`"$q`" ConnectionEndPoint=`"$c`" Name=`"$name`" Description=`"Local Owen server`" Map=`"`" Mission=`"`" MaxPlayers=`"8`" ServerVersion=`"0`" RequiredVersion=`"128`" RequiredBuild=`"0`" AllowedBuild=`"0`" RequirePassword=`"0`" IsVacEnabled=`"0`" Tags=`"local`" IsThirdPersonViewEnabled=`"1`" RequiresExpansionTerrain=`"0`" />"
        )
    }
}

$dir = Split-Path $favPath -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

$xml = @"
<?xml version="1.0" encoding="windows-1252" ?>
<FavoriteServers>
$($entries -join "`n")
</FavoriteServers>
"@

Set-Content -Path $favPath -Value $xml -Encoding UTF8
Write-Host "Wrote $($entries.Count) favorites to $favPath"
Write-Host "DayZ Launcher -> Servers -> Remote -> Favorites"
