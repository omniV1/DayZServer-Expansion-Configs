# Sync configured map Workshop folders into the DayZServer root and copy bikeys.
param(
    [string]$Map = 'all',
    [string]$WorkshopRoot = 'C:\Games\Steam\steamapps\workshop\content\221100',
    [switch]$OpenMissingWorkshopPages
)

$ErrorActionPreference = 'Stop'
$ServerRoot = Split-Path $PSScriptRoot -Parent
$CatalogPath = Join-Path $PSScriptRoot 'map_workshop_catalog.json'
$Catalog = Get-Content $CatalogPath -Raw | ConvertFrom-Json
$KeysDir = Join-Path $ServerRoot 'keys'

if (-not (Test-Path $KeysDir)) {
    New-Item -ItemType Directory -Path $KeysDir -Force | Out-Null
}

function Copy-ModKeys {
    param([string]$Dest)

    $keyRoot = Join-Path $Dest 'keys'
    if (-not (Test-Path $keyRoot)) { $keyRoot = Join-Path $Dest 'Keys' }
    if (-not (Test-Path $keyRoot)) { return }
    foreach ($key in Get-ChildItem $keyRoot -Filter '*.bikey' -ErrorAction SilentlyContinue) {
        Copy-Item -LiteralPath $key.FullName -Destination (Join-Path $KeysDir $key.Name) -Force
        Write-Host "  Key: $($key.Name)"
    }
}

function Sync-Map {
    param([string]$Name, $Info)

    $id = [string]$Info.workshop_id
    $destName = [string]$Info.server_mod_folder
    $src = Join-Path $WorkshopRoot $id
    $dst = Join-Path $ServerRoot $destName

    Write-Host "`n=== $Name ($id -> $destName) ===" -ForegroundColor Cyan
    if (-not (Test-Path $src)) {
        Write-Host "Missing Workshop folder: $src" -ForegroundColor Yellow
        Write-Host "Subscribe/download first: https://steamcommunity.com/sharedfiles/filedetails/?id=$id"
        if ($OpenMissingWorkshopPages) {
            Start-Process "steam://openurl/https://steamcommunity.com/sharedfiles/filedetails/?id=$id"
        }
        return
    }

    if (-not (Test-Path $dst)) {
        New-Item -ItemType Directory -Path $dst -Force | Out-Null
    }
    robocopy $src $dst /MIR /XD keys Keys /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Warning "Robocopy exit $LASTEXITCODE for $destName"
    } else {
        Write-Host "Synced $destName"
    }
    Copy-ModKeys -Dest $src
    Copy-ModKeys -Dest $dst
}

if ($Map -eq 'all') {
    foreach ($p in $Catalog.PSObject.Properties) {
        Sync-Map -Name $p.Name -Info $p.Value
    }
} else {
    $info = $Catalog.$Map
    if (-not $info) {
        $known = ($Catalog.PSObject.Properties.Name -join ', ')
        throw "Unknown map '$Map'. Known maps: $known"
    }
    Sync-Map -Name $Map -Info $info
}
