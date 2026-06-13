# Quick check: did the last server start load Takistan terrain?
$root = Split-Path $PSScriptRoot -Parent
$rpt = $null
foreach ($dir in @('profiles_takistan', 'profiles')) {
    $folder = Join-Path $root $dir
    if (-not (Test-Path $folder)) { continue }
    $candidate = Get-ChildItem (Join-Path $folder 'DayZServer_x64_*.RPT') -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($candidate -and (-not $rpt -or $candidate.LastWriteTime -gt $rpt.LastWriteTime)) {
        $rpt = $candidate
    }
}
if (-not $rpt) { Write-Host 'No RPT found.'; exit 1 }

Write-Host "Latest log: $($rpt.Name)"
$lines = Get-Content $rpt.FullName -TotalCount 5
$cmd = $lines | Where-Object { $_ -match '^==.*exe' } | Select-Object -Last 1
Write-Host $cmd

$text = Get-Content $rpt.FullName -Raw
if ($text -match '-mod=%DAYZ_MODS%') {
    Write-Host 'FAIL: -mod= was literal %DAYZ_MODS% (batch start bug). Use Launch-Takistan.ps1' -ForegroundColor Red
    exit 1
}
if ($text -match '@Dabs/Anims' -and $text -notmatch '@Dabs Framework\\addons\\Scripts\.pbo') {
    Write-Host 'FAIL: -mod= split at @Dabs Framework - @TakistanPlus not loaded. Use Launch-Takistan.ps1 (not Start-Process) or start_Takistan_DIRECT.cmd' -ForegroundColor Red
    exit 1
}
if ($text -notmatch '@TakistanPlus\\addons\\Takistan\.pbo|@TakistanPlus\\addons\\Takistan_Map\.pbo') {
    Write-Host 'FAIL: @TakistanPlus terrain not loaded. Quote the full -mod= line.' -ForegroundColor Red
    exit 1
}
if ($text -notmatch 'mpmissions\\dayzOffline\.TakistanPlus|storage_\d+') {
    Write-Host 'FAIL: Mission did not load (use template dayzOffline.TakistanPlus in serverDZ_Takistan.cfg).' -ForegroundColor Red
    Write-Host '      "No world with the name Takistan" means old template dayzOffline.Takistan — world is TakistanPlus now.' -ForegroundColor Yellow
    exit 1
}
if ($text -notmatch 'Takistan_Map|Takistan\\|@TakistanPlus\\addons\\Takistan') {
    Write-Host 'FAIL: Takistan terrain PBOs not loaded' -ForegroundColor Red
    exit 1
}
if ($text -notmatch '@Dabs Framework\\addons\\Scripts\.pbo') {
    Write-Host 'FAIL: @Dabs Framework not loaded (sandstorm needs WeatherEvent). Put @Dabs Framework BEFORE @TakistanPlus in -mod=' -ForegroundColor Red
    exit 1
}
if ($text -match 'sandstorm\.c.*Unknown type') {
    Write-Host 'FAIL: Sandstorm compile error - update Dabs Framework on server+client (Workshop) and keep @Dabs before @TakistanPlus' -ForegroundColor Red
    exit 1
}
Write-Host 'OK: Takistan + Dabs loaded.' -ForegroundColor Green
