# Copy Namalsk server mods to the DayZ client so PBO hashes match (fixes LEHS / character_proxies kick).
# Run with DayZServer_x64 stopped. DayZ client should be closed too.

$ErrorActionPreference = 'Stop'
$ServerRoot = "C:\Games\Steam\steamapps\common\DayZServer"
$ClientWorkshop = "C:\Games\Steam\steamapps\common\DayZ\!Workshop"
$WorkshopRoot = "C:\Games\Steam\steamapps\workshop\content\221100"

$mods = @(
    @{ Name = '@Namalsk Island'; WorkshopId = '2289456201' },
    @{ Name = '@Namalsk Survival (server)'; WorkshopId = '2288336145' }
)

if (-not (Test-Path $ClientWorkshop)) {
    New-Item -ItemType Directory -Path $ClientWorkshop -Force | Out-Null
}

foreach ($m in $mods) {
    $src = Join-Path $ServerRoot $m.Name
    if (-not (Test-Path $src)) {
        $alt = Join-Path $WorkshopRoot $m.WorkshopId
        if (Test-Path $alt) { $src = $alt }
    }
    if (-not (Test-Path $src)) {
        Write-Warning "Missing $($m.Name) on server/workshop"
        continue
    }

    $dst = Join-Path $ClientWorkshop $m.Name
    Write-Host "Sync $($m.Name) -> client !Workshop ..."
    if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Path $dst -Force | Out-Null }
    robocopy $src $dst /MIR /XD keys /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) { Write-Warning "Robocopy exit $LASTEXITCODE for $($m.Name)" }

    $srcKeys = Join-Path $src 'keys'
    $dstKeys = Join-Path $dst 'keys'
    if (Test-Path $srcKeys) {
        if (-not (Test-Path $dstKeys)) { New-Item -ItemType Directory -Path $dstKeys | Out-Null }
        robocopy $srcKeys $dstKeys /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    }
}

Write-Host ""
Write-Host "Done. In DayZ Launcher -> MODS, enable BOTH:"
Write-Host "  @Namalsk Island"
Write-Host "  @Namalsk Survival (server)"
Write-Host "Then join Namalsk (same order as server: Island before other mods)."
