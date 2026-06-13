# Apply Expansion spawn + AI setup to Namalsk, Livonia (Enoch), Sakhal, and Takistan.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
python (Join-Path $PSScriptRoot 'build_map_expansion.py') --all
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python (Join-Path $PSScriptRoot 'build_map_expansion.py') chernarus --gear-only
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ''
Write-Host 'Done. Restart each map server to load spawn gear + settings.'
