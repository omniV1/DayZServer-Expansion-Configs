# Build the DayZ Server Control Center Windows executable with PyInstaller.
#
# Optional Authenticode signing: pass -CertThumbprint <thumbprint> to sign the
# exe with a code-signing certificate already installed in your certificate store
# (this is how hardware-token / cloud certs like Certum or an EV cert present
# themselves). Requires signtool.exe from the Windows SDK on PATH. Without a
# thumbprint the build is unsigned, which is fine for open-source distribution -
# see the "Why Windows may warn you" notes in README.md / QUICKSTART.md.
param(
    [string]$Version = '1.7.0',
    [string]$CertThumbprint = '',
    [string]$TimestampUrl = 'http://timestamp.digicert.com'
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

# One-folder build (--onedir): the exe ships next to its dependencies in a
# DayZServerControlCenter\ subfolder. This trips antivirus heuristics far less
# than a packed --onefile exe (which unpacks to a temp dir at runtime) and
# starts faster.
$addData = "$ControlCenterUi;control_center"
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
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

$exePath = Join-Path $OutputDir 'DayZServerControlCenter\DayZServerControlCenter.exe'

# Optional Authenticode signing (only when a cert thumbprint is supplied).
if ($CertThumbprint) {
    $signtool = (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
    if (-not $signtool) {
        throw 'signtool.exe not found on PATH. Install the Windows SDK or omit -CertThumbprint.'
    }
    Write-Host "Signing $exePath with certificate $CertThumbprint"
    & $signtool sign /sha1 $CertThumbprint /fd sha256 /tr $TimestampUrl /td sha256 $exePath
    if ($LASTEXITCODE -ne 0) {
        throw 'Code signing failed.'
    }
    & $signtool verify /pa $exePath | Out-Null
}

$readme = @"
DayZ Server Control Center $Version

Open the DayZServerControlCenter folder and run DayZServerControlCenter.exe.
Keep that folder intact - the exe needs the files next to it. You can make a
Desktop shortcut to the exe if you like.

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

# Publish a SHA-256 checksum next to the zip so downloaders can verify the file.
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower()
$sha256Path = "$zip.sha256"
Set-Content -LiteralPath $sha256Path -Value "$hash  DayZServerControlCenter-$Version-windows.zip" -Encoding ASCII

Write-Host "Built $zip"
Write-Host "SHA-256: $hash"
Write-Host "Checksum file: $sha256Path"
