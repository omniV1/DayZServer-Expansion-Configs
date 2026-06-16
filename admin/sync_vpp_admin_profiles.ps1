# Sync VPPAdminTools admin credentials into each configured map profile.
param(
    [string]$Map = 'all',

    [string]$SourceProfile = 'profiles',

    [switch]$Overwrite
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$LaunchPath = Join-Path $Root 'admin\map_launch.json'
if (-not (Test-Path $LaunchPath)) { throw "Missing $LaunchPath" }

function Resolve-InRoot {
    param([string]$RelativePath)
    $path = Join-Path $Root $RelativePath
    $resolved = [System.IO.Path]::GetFullPath($path)
    $rootResolved = [System.IO.Path]::GetFullPath($Root)
    if (-not $resolved.StartsWith($rootResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to use path outside server root: $RelativePath"
    }
    return $resolved
}

function Copy-PrivateFile {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Label
    )
    if (-not (Test-Path $Source)) { throw "Missing source $Label at $Source" }
    if ((Test-Path $Destination) -and -not $Overwrite) {
        return 'exists'
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    return 'copied'
}

$launch = Get-Content $LaunchPath -Raw | ConvertFrom-Json
$maps = if ($Map -eq 'all') {
    $launch.maps.PSObject.Properties
} else {
    $cfg = $launch.maps.$Map
    if (-not $cfg) {
        $known = ($launch.maps.PSObject.Properties.Name -join ', ')
        throw "Unknown map: $Map. Known maps: $known"
    }
    @([pscustomobject]@{ Name = $Map; Value = $cfg })
}

$sourceRoot = Resolve-InRoot $SourceProfile
$sourcePerms = Join-Path $sourceRoot 'VPPAdminTools\Permissions'
$sourceCredentials = Join-Path $sourcePerms 'credentials.txt'
$sourceSuperAdmins = Join-Path $sourcePerms 'SuperAdmins\SuperAdmins.txt'

Write-Host "VPP profile sync"
Write-Host "  Source profile: $SourceProfile"
Write-Host "  Map target: $Map"
Write-Host "  Overwrite: $Overwrite"
Write-Host ""

foreach ($entry in $maps) {
    $name = $entry.Name
    $profileDir = $entry.Value.profiles_dir
    $targetRoot = Resolve-InRoot $profileDir
    $targetPerms = Join-Path $targetRoot 'VPPAdminTools\Permissions'
    $targetCredentials = Join-Path $targetPerms 'credentials.txt'
    $targetSuperAdmins = Join-Path $targetPerms 'SuperAdmins\SuperAdmins.txt'

    $credStatus = Copy-PrivateFile -Source $sourceCredentials -Destination $targetCredentials -Label 'VPP credentials.txt'
    $adminStatus = Copy-PrivateFile -Source $sourceSuperAdmins -Destination $targetSuperAdmins -Label 'VPP SuperAdmins.txt'

    Write-Host ("  {0,-10} credentials={1,-6} superadmins={2,-6} profile={3}" -f $name, $credStatus, $adminStatus, $profileDir)
}

Write-Host ""
Write-Host "Restart affected DayZ servers after syncing VPP profile files."
