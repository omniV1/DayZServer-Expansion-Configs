# Check that active launch profiles are using VPP admin tooling cleanly.
param(
    [string]$Map = 'all',

    [switch]$IncludeClientProfiles,

    [switch]$CheckDesktop,

    [string]$DesktopDir = (Join-Path $env:USERPROFILE 'OneDrive\Desktop\games\DayZ')
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$LaunchPath = Join-Path $Root 'admin\map_launch.json'
if (-not (Test-Path $LaunchPath)) { throw "Missing $LaunchPath" }

$Launch = Get-Content $LaunchPath -Raw | ConvertFrom-Json
$ForbiddenAdminPatterns = @('@Community-Online-Tools', '1564026768', 'JM/COT')

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

function Get-MapEntries {
    if ($Map -eq 'all') {
        return $Launch.maps.PSObject.Properties
    }

    $cfg = $Launch.maps.$Map
    if (-not $cfg) {
        $known = ($Launch.maps.PSObject.Properties.Name -join ', ')
        throw "Unknown map: $Map. Known maps: $known"
    }
    return @([pscustomobject]@{ Name = $Map; Value = $cfg })
}

function Test-ForbiddenAdminText {
    param([string]$Text)

    foreach ($needle in $ForbiddenAdminPatterns) {
        if ($Text -like "*$needle*") { return $needle }
    }
    return $null
}

function Test-ModList {
    param([object]$Cfg)

    $modsFileName = if ($Cfg.mods_file) { $Cfg.mods_file } elseif ($Launch.mods_file) { $Launch.mods_file } else { 'chernarus_mods.txt' }
    $modsPath = Join-Path $Root (Join-Path 'admin' $modsFileName)
    if (-not (Test-Path $modsPath)) { return "FAIL missing $modsFileName" }

    $parts = New-Object System.Collections.Generic.List[string]
    $parts.Add((Get-Content $modsPath -Raw))
    if ($Cfg.prepend_mods) { foreach ($m in @($Cfg.prepend_mods)) { $parts.Add([string]$m) } }
    if ($Cfg.extra_mods) { foreach ($m in @($Cfg.extra_mods)) { $parts.Add([string]$m) } }
    if ($Cfg.server_mods) { foreach ($m in @($Cfg.server_mods)) { $parts.Add([string]$m) } }
    $text = ($parts -join ';')

    $forbidden = Test-ForbiddenAdminText -Text $text
    if ($forbidden) { return "FAIL COT active: $forbidden" }
    if ($text -notlike '*@VPPAdminTools*') { return 'FAIL missing @VPPAdminTools' }
    if (-not (Test-Path (Join-Path $Root '@VPPAdminTools'))) { return 'WARN VPP folder missing' }
    return 'ok'
}

function Test-VppProfile {
    param([string]$ProfileDir)

    $profileRoot = Resolve-InRoot $ProfileDir
    $credentials = Join-Path $profileRoot 'VPPAdminTools\Permissions\credentials.txt'
    $superAdmins = Join-Path $profileRoot 'VPPAdminTools\Permissions\SuperAdmins\SuperAdmins.txt'

    $missing = @()
    if (-not (Test-Path $credentials)) { $missing += 'credentials' }
    elseif ((Get-Item $credentials).Length -le 0) { $missing += 'credentials-empty' }
    if (-not (Test-Path $superAdmins)) { $missing += 'superadmins' }
    elseif ((Get-Item $superAdmins).Length -le 0) { $missing += 'superadmins-empty' }

    if ($missing.Count -gt 0) { return 'FAIL ' + ($missing -join ',') }
    return 'ok'
}

function Test-InputPreset {
    param([string]$Path)

    if (-not (Test-Path $Path)) { return 'WARN preset missing' }

    try {
        [xml]$xml = Get-Content -LiteralPath $Path -Raw
    } catch {
        return "FAIL parse: $($_.Exception.Message)"
    }

    if (-not $xml.preset) { return 'FAIL missing preset root' }

    $inputs = @($xml.preset.input)
    $cotCount = @($inputs | Where-Object { ([string]$_.name).StartsWith('UACOT', [System.StringComparison]::OrdinalIgnoreCase) }).Count
    $toggle = @($inputs | Where-Object { $_.name -eq 'UAToggleAdminTools' } | Select-Object -First 1)
    $open = @($inputs | Where-Object { $_.name -eq 'UAOpenAdminTools' } | Select-Object -First 1)
    $toggleKey = if ($toggle.Count -gt 0 -and $toggle[0].btn) { [string]$toggle[0].btn.name } else { '' }
    $openKey = if ($open.Count -gt 0 -and $open[0].btn) { [string]$open[0].btn.name } else { '' }

    $issues = @()
    if ($cotCount -gt 0) { $issues += "COT inputs=$cotCount" }
    if ($toggleKey -ne 'kEnd') { $issues += "toggle=$toggleKey" }
    if ($openKey -ne 'kHome') { $issues += "open=$openKey" }

    if ($issues.Count -gt 0) { return 'FAIL ' + ($issues -join ', ') }
    return 'ok'
}

function Test-DesktopLauncher {
    param([string]$MapName)

    if (-not (Test-Path $DesktopDir)) { return 'WARN desktop dir missing' }

    $files = @(Get-ChildItem -LiteralPath $DesktopDir -Filter 'start_*.bat' -File -ErrorAction SilentlyContinue)
    $matching = @()
    foreach ($file in $files) {
        $text = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
        if ($text -match "(?i)-Map\s+$([regex]::Escape($MapName))\b") {
            $matching += [pscustomobject]@{ File = $file; Text = $text }
        }
    }

    if ($matching.Count -eq 0) { return 'WARN launcher missing' }

    foreach ($entry in $matching) {
        $text = $entry.Text
        $forbidden = Test-ForbiddenAdminText -Text $text
        if ($forbidden) { return "FAIL desktop COT: $($entry.File.Name)" }
        if ($text -notmatch 'Launch-DayZMap\.ps1') { return "FAIL desktop legacy: $($entry.File.Name)" }
    }
    return 'ok'
}

function Test-RecentLog {
    param([string]$ProfileDir)

    $profileRoot = Resolve-InRoot $ProfileDir
    if (-not (Test-Path $profileRoot)) { return 'no profile' }

    $latest = Get-ChildItem -LiteralPath $profileRoot -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @('.RPT', '.log') } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $latest) { return 'no log' }

    $tail = Get-Content -LiteralPath $latest.FullName -Tail 500 -ErrorAction SilentlyContinue
    $cli = @($tail | Where-Object { $_ -like '*CLI params:*' } | Select-Object -Last 1)
    if ($cli.Count -eq 0) { return "log $($latest.Name)" }

    $line = [string]$cli[0]
    $forbidden = Test-ForbiddenAdminText -Text $line
    if ($forbidden) { return "WARN latest CLI has COT" }
    if ($line -like '*@VPPAdminTools*') { return "ok $($latest.Name)" }
    return "WARN latest CLI lacks VPP"
}

function Test-RunningProcesses {
    $procs = @(Get-CimInstance Win32_Process -Filter "Name = 'DayZServer_x64.exe'" -ErrorAction SilentlyContinue)
    if ($procs.Count -eq 0) {
        Write-Host 'Running DayZ servers: none'
        return 0
    }

    $bad = 0
    Write-Host "Running DayZ servers: $($procs.Count)"
    foreach ($proc in $procs) {
        $cmd = [string]$proc.CommandLine
        $admin = if ($cmd -like '*@Community-Online-Tools*') { 'COT' } elseif ($cmd -like '*@VPPAdminTools*') { 'VPP' } else { 'unknown' }
        $flag = if ($admin -eq 'COT') { $bad++ ; 'FAIL' } else { 'ok' }
        Write-Host ("  PID {0,-7} admin={1,-7} {2}" -f $proc.ProcessId, $admin, $flag)
    }
    return $bad
}

$entries = Get-MapEntries
$failures = 0
$warnings = 0

Write-Host 'Admin tooling check'
Write-Host '  Expected admin mod: @VPPAdminTools'
Write-Host '  Rejected admin mod: @Community-Online-Tools'
Write-Host ''

$failures += Test-RunningProcesses
Write-Host ''

Write-Host ("{0,-10} {1,-24} {2,-24} {3,-28} {4,-24} {5}" -f 'Map', 'Mods', 'VPP profile', 'Server input', 'Desktop', 'Recent log')
Write-Host ('-' * 126)
foreach ($entry in $entries) {
    $name = $entry.Name
    $cfg = $entry.Value
    $profileDir = if ($cfg.profiles_dir) { $cfg.profiles_dir } else { "profiles_$name" }
    $presetPath = Join-Path (Resolve-InRoot $profileDir) 'Users\Survivor\Server.dayz_preset_User.xml'

    $mods = Test-ModList -Cfg $cfg
    $profile = Test-VppProfile -ProfileDir $profileDir
    $input = Test-InputPreset -Path $presetPath
    $desktop = if ($CheckDesktop) { Test-DesktopLauncher -MapName $name } else { 'skip' }
    $recentLog = Test-RecentLog -ProfileDir $profileDir

    foreach ($status in @($mods, $profile, $input, $desktop, $recentLog)) {
        if ($status -like 'FAIL*') { $failures++ }
        elseif ($status -like 'WARN*') { $warnings++ }
    }

    Write-Host ("{0,-10} {1,-24} {2,-24} {3,-28} {4,-24} {5}" -f $name, $mods, $profile, $input, $desktop, $recentLog)
}

$sharedPresets = @(
    (Join-Path $Root 'Server.dayz_preset_User.xml'),
    (Join-Path $Root 'config\Users\Survivor\Server.dayz_preset_User.xml')
)
$clientPresets = @{}

if ($IncludeClientProfiles) {
    $dayzDirs = @(
        (Join-Path $env:USERPROFILE 'Documents\DayZ'),
        (Join-Path $env:USERPROFILE 'OneDrive\Documents\DayZ')
    )
    foreach ($dir in $dayzDirs) {
        if (Test-Path $dir) {
            $sharedPresets += @(
                Get-ChildItem -LiteralPath $dir -Filter '*.xml' -File -ErrorAction SilentlyContinue |
                    Where-Object {
                        $_.Name -like '*.dayz_preset_User.xml' -or
                        $_.Name -like '*.preset_X1MouseKey.xml'
                    } |
                    ForEach-Object {
                        $clientPresets[$_.FullName] = $true
                        $_.FullName
                    }
            )
        }
    }
}

Write-Host ''
Write-Host 'Shared/client input presets:'
foreach ($preset in ($sharedPresets | Select-Object -Unique)) {
    $status = Test-InputPreset -Path $preset
    if ($clientPresets.ContainsKey($preset) -and $status -like 'FAIL*') {
        $status = $status -replace '^FAIL', 'WARN client'
    }

    if ($status -like 'FAIL*') { $failures++ }
    elseif ($status -like 'WARN*') { $warnings++ }
    Write-Host "  $status`t$preset"
}

Write-Host ''
Write-Host "Summary: failures=$failures warnings=$warnings"
if ($failures -gt 0) {
    Write-Host 'Repair helpers:'
    Write-Host '  powershell -ExecutionPolicy Bypass -File admin\sync_vpp_admin_profiles.ps1 -Map all'
    Write-Host '  powershell -ExecutionPolicy Bypass -File admin\switch_admin_inputs_to_vpp.ps1 -Map all -IncludeClientProfiles'
    exit 1
}
exit 0
