# Verify map launcher: ports, mod folders, latest RPT -mod= line
param(
    [ValidateSet('chernarus', 'enoch', 'sakhal', 'namalsk', 'all')]
    [string]$Map = 'all'
)

$Root = Split-Path $PSScriptRoot -Parent
$Launch = Get-Content (Join-Path $Root 'admin\map_launch.json') -Raw | ConvertFrom-Json
$ModsRaw = (Get-Content (Join-Path $Root 'admin\chernarus_mods.txt') -Raw).Trim()

function Test-MapLaunch {
    param($Name, $Cfg)

    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    Write-Host "  Port: $($Cfg.port) | steam_query: $($Cfg.steam_query_port)"
    Write-Host "  Config: $($Cfg.config)"

    $missing = @()
    foreach ($m in ($ModsRaw -split ';')) {
        $m = $m.Trim()
        if (-not $m) { continue }
        if (-not (Test-Path -LiteralPath (Join-Path $Root $m))) { $missing += $m }
    }
    if ($Cfg.prepend_mods) {
        foreach ($m in $Cfg.prepend_mods) {
            if (-not (Test-Path -LiteralPath (Join-Path $Root $m))) { $missing += $m }
        }
    }
    if ($Cfg.extra_mods) {
        foreach ($m in $Cfg.extra_mods) {
            if (-not (Test-Path -LiteralPath (Join-Path $Root $m))) { $missing += $m }
        }
    }
    if ($missing.Count) {
        Write-Host "  MISSING mod folders:" -ForegroundColor Red
        $missing | ForEach-Object { Write-Host "    $_" }
    } else {
        Write-Host "  All listed mod folders present." -ForegroundColor Green
    }

    $rpt = Get-ChildItem (Join-Path $Root 'profiles') -Filter 'DayZServer_x64_*.RPT' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($rpt) {
        $line = Get-Content $rpt.FullName -TotalCount 3 | Select-Object -First 1
        if ($line -match '-mod=') {
            if ($line -match '%DAYZ_MODS%') {
                Write-Host "  RPT BAD: unexpanded %DAYZ_MODS%" -ForegroundColor Red
            } elseif ($line -notmatch '@Dabs Framework') {
                Write-Host "  RPT WARN: -mod= may be truncated (no @Dabs Framework in line 1)" -ForegroundColor Yellow
            } else {
                Write-Host "  Latest RPT has quoted -mod= with @Dabs Framework (OK)." -ForegroundColor Green
            }
            if ($line -match "port=$($Cfg.port)") {
                Write-Host "  RPT matches game port $($Cfg.port)." -ForegroundColor Green
            }
        }
        Write-Host "  RPT: $($rpt.Name)"
    }

    $listener = Get-NetTCPConnection -LocalPort $Cfg.port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        Write-Host "  Port $($Cfg.port) is IN USE (server may already be running)." -ForegroundColor Yellow
    }
}

$maps = if ($Map -eq 'all') { $Launch.maps.PSObject.Properties } else { @($Launch.maps.$Map | ForEach-Object { [pscustomobject]@{ Name = $Map; Value = $_ } }) }
if ($Map -eq 'all') {
    foreach ($p in $Launch.maps.PSObject.Properties) { Test-MapLaunch $p.Name $p.Value }
} else {
    Test-MapLaunch $Map $Launch.maps.$Map
}

Write-Host "`nLauncher tip: wait for RPT 'Init sequence finished' before joining."
Write-Host "Chernarus/Enoch may show only ~9 mods (Steam packet limit); load the full list in the DayZ client mod launcher."
