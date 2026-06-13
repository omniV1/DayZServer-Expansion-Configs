# Sync server mods from client Steam Workshop (fixes kick 146 and stale PBOs).
# Run with server STOPPED. Requires admin if files are locked.

$WorkshopRoot = "C:\Games\Steam\steamapps\workshop\content\221100"
$ServerRoot = "C:\Games\Steam\steamapps\common\DayZServer"
$KeysDir = Join-Path $ServerRoot "keys"

$Map = @{
    "2572331007" = "@DayZ-Expansion-Bundle"
    "2291785308" = "@DayZ-Expansion-Core"
    "2792982069" = "@DayZ-Expansion-AI"
    "2116157322" = "@DayZ-Expansion-Licensed"
    "2572328470" = "@DayZ-Expansion-Market"
    "2419315705" = "@Techs Weapon Mod"
    "2143128974" = "@Advanced Weapon Scopes"
    "2545327648" = "@Dabs Framework"
    "1559212036" = "@CF"
}

function Sync-ModFolder {
    param([string]$WorkshopId, [string]$DestName)

    $src = Join-Path $WorkshopRoot $WorkshopId
    $dst = Join-Path $ServerRoot $DestName
    if (-not (Test-Path $src)) {
        Write-Warning "Missing workshop mod $WorkshopId -> $DestName"
        return
    }
    if (-not (Test-Path $dst)) {
        Write-Warning "Missing server folder $dst"
        return
    }
    Write-Host "Syncing $DestName ..."
    robocopy $src $dst /MIR /XD keys /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Warning "Robocopy reported errors for $DestName (exit $LASTEXITCODE)"
    } else {
        Write-Host "  OK"
    }
}

function Copy-ModKeys {
    param([string]$DestName)

    $modKeys = Join-Path (Join-Path $ServerRoot $DestName) "keys"
    if (-not (Test-Path $modKeys)) { return }
    foreach ($key in Get-ChildItem $modKeys -Filter "*.bikey" -ErrorAction SilentlyContinue) {
        $target = Join-Path $KeysDir $key.Name
        if (-not (Test-Path $target)) {
            Copy-Item $key.FullName $target
            Write-Host "  Key: $($key.Name)"
        }
    }
}

if (-not (Test-Path $KeysDir)) {
    New-Item -ItemType Directory -Path $KeysDir | Out-Null
}

foreach ($id in $Map.Keys) {
    Sync-ModFolder -WorkshopId $id -DestName $Map[$id]
    Copy-ModKeys -DestName $Map[$id]
}

Write-Host "Done. Restart DayZ server and retry client connect."
