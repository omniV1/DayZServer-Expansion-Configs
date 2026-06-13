# Run once after LEHS / character_proxies kick (0x00040009). Stop Namalsk server first.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent

Write-Host 'Namalsk Expansion spawn + AI (1-2 AI per town/village)...'
python (Join-Path $PSScriptRoot 'build_map_expansion.py') namalsk
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'Syncing Namalsk mod files to client...'
& (Join-Path $PSScriptRoot 'sync_namalsk_to_client.ps1')

Write-Host 'Refreshing Owens-Namalsk launcher preset...'
& (Join-Path $PSScriptRoot 'install_namalsk_mod_preset.ps1')

$server = Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue
if ($server) {
    Write-Host 'Stop DayZServer_x64 before resetting character save.'
} else {
    & (Join-Path $PSScriptRoot 'reset_namalsk_character.ps1')
}

Write-Host ''
Write-Host 'IMPORTANT: Restart Namalsk server so -mod= includes @Namalsk Survival (server).'
Write-Host 'In latest RPT you should see both Namalsk mods inside -mod= not only -serverMod=.'
Write-Host 'Next: Launcher -> Owens-Namalsk preset -> PLAY -> connect 127.0.0.1:2502'
