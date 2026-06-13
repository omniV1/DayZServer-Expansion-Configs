# Mirror Workshop TakistanPlus (2563233742) to server @TakistanPlus and copy bikey to server keys/.
# Run with DayZServer_x64 stopped.

$ErrorActionPreference = 'Stop'
$ServerRoot = 'C:\Games\Steam\steamapps\common\DayZServer'
$Workshop = 'C:\Games\Steam\steamapps\workshop\content\221100\2563233742'
$Dst = Join-Path $ServerRoot '@TakistanPlus'
$Keys = Join-Path $ServerRoot 'keys'

if (-not (Test-Path $Workshop)) {
    Write-Host 'Subscribe to TakistanPlus in Steam (Workshop 2563233742), wait for download, then re-run.' -ForegroundColor Red
    exit 1
}

Write-Host "Sync $Workshop -> $Dst"
if (-not (Test-Path $Dst)) { New-Item -ItemType Directory -Path $Dst -Force | Out-Null }
robocopy $Workshop $Dst /MIR /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Warning "Robocopy exit $LASTEXITCODE" }

$keySrc = Join-Path $Workshop 'Keys\CypeRevenge.bikey'
if (Test-Path $keySrc) {
    if (-not (Test-Path $Keys)) { New-Item -ItemType Directory -Path $Keys | Out-Null }
    Copy-Item $keySrc (Join-Path $Keys 'CypeRevenge.bikey') -Force
    Write-Host 'Copied CypeRevenge.bikey -> keys\'
}

Write-Host 'Done. Restart Takistan with Launch-DayZMap.ps1 -Map takistan'
