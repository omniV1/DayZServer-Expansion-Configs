# Build the DayZ Server Control Center Windows executable with PyInstaller.
param(
    [string]$Version = '0.5.1'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$DistRoot = Join-Path $Root 'dist'
$OutputDir = Join-Path $DistRoot "DayZServerControlCenter-$Version-windows"
$WorkDir = Join-Path $Root 'local_runtime\pyinstaller'
$SpecDir = Join-Path $Root 'local_runtime\pyinstaller_spec'
$EntryScript = Join-Path $Root 'admin\control_center.py'
$ControlCenterUi = Join-Path $Root 'admin\control_center'

Set-Location $Root

python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is not installed. Run: python -m pip install pyinstaller'
}

if (Test-Path $OutputDir) {
    Remove-Item -LiteralPath $OutputDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$addData = "$ControlCenterUi;control_center"
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name DayZServerControlCenter `
    --distpath $OutputDir `
    --workpath $WorkDir `
    --specpath $SpecDir `
    --add-data $addData `
    $EntryScript

if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller build failed.'
}

$readme = @"
DayZ Server Control Center $Version

Run DayZServerControlCenter.exe.

On first launch, choose your DayZServer folder if it is not auto-detected.
The selected folder must contain:
- admin\map_launch.json
- Launch-DayZMap.ps1

The app binds to 127.0.0.1 and opens your browser automatically.
"@

Set-Content -LiteralPath (Join-Path $OutputDir 'README.txt') -Value $readme -Encoding ASCII

$zip = Join-Path $DistRoot "DayZServerControlCenter-$Version-windows.zip"
if (Test-Path $zip) {
    Remove-Item -LiteralPath $zip -Force
}
Compress-Archive -Path (Join-Path $OutputDir '*') -DestinationPath $zip -Force

Write-Host "Built $zip"
