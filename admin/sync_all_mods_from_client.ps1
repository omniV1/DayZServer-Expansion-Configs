# Mirror client !Workshop mods onto server @folders (fixes MODIFIED_DATA / script kicks).
# Run with all DayZServer_x64 processes stopped.

$ErrorActionPreference = 'Stop'
$ClientWorkshop = "C:\Games\Steam\steamapps\common\DayZ\!Workshop"
$ServerRoot = "C:\Games\Steam\steamapps\common\DayZServer"
$KeysDir = Join-Path $ServerRoot 'keys'
$ModsFile = Join-Path $ServerRoot 'admin\chernarus_mods.txt'

if (-not (Test-Path $ClientWorkshop)) { throw "Missing $ClientWorkshop" }
if (-not (Test-Path $ModsFile)) { throw "Missing $ModsFile" }

$mods = (Get-Content $ModsFile -Raw).Trim().TrimEnd(';').Split(';') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if (-not (Test-Path $KeysDir)) { New-Item -ItemType Directory -Path $KeysDir | Out-Null }

foreach ($mod in $mods) {
    $src = Join-Path $ClientWorkshop $mod
    $dst = Join-Path $ServerRoot $mod
    if (-not (Test-Path $src)) {
        Write-Warning "Client mod missing: $mod"
        continue
    }
    if (-not (Test-Path $dst)) {
        Write-Warning "Server folder missing, creating: $mod"
        New-Item -ItemType Directory -Path $dst -Force | Out-Null
    }
    Write-Host "Sync $mod ..."
    robocopy $src $dst /MIR /XD keys /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) { Write-Warning "Robocopy exit $LASTEXITCODE for $mod" }

    $modKeys = Join-Path $src 'keys'
    if (Test-Path $modKeys) {
        foreach ($key in Get-ChildItem $modKeys -Filter '*.bikey' -ErrorAction SilentlyContinue) {
            $target = Join-Path $KeysDir $key.Name
            if (-not (Test-Path $target)) { Copy-Item $key.FullName $target }
        }
    }
}

$namalskMods = @(
    @{ Name = '@Namalsk Island'; WorkshopId = '2289456201' },
    @{ Name = '@Namalsk Survival (server)'; WorkshopId = '2288336145' }
)
foreach ($nm in $namalskMods) {
    $namSrc = Join-Path $ClientWorkshop $nm.Name
    if (-not (Test-Path $namSrc)) {
        $namSrc = Join-Path "C:\Games\Steam\steamapps\workshop\content\221100" $nm.WorkshopId
    }
    $namDst = Join-Path $ServerRoot $nm.Name
    if ((Test-Path $namSrc) -and (Test-Path $namDst)) {
        Write-Host "Sync $($nm.Name) ..."
        robocopy $namSrc $namDst /MIR /XD keys /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
        $nk = Join-Path $namSrc 'keys'
        if (Test-Path $nk) {
            foreach ($key in Get-ChildItem $nk -Filter '*.bikey' -ErrorAction SilentlyContinue) {
                $target = Join-Path $KeysDir $key.Name
                if (-not (Test-Path $target)) { Copy-Item $key.FullName $target }
            }
        }
    }
}

Write-Host "Done. Restart servers and client."
