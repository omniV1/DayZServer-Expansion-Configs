# Remove stale COT input bindings and ensure VPP admin hotkeys are present.
param(
    [string]$Map = 'all',

    [switch]$IncludeClientProfiles
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$LaunchPath = Join-Path $Root 'admin\map_launch.json'
if (-not (Test-Path $LaunchPath)) { throw "Missing $LaunchPath" }

function Backup-File {
    param([string]$Path)
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $relative = if ($Path.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        $Path.Substring($Root.Length).TrimStart('\')
    } else {
        ($Path -replace '^[A-Za-z]:\\', '') -replace '[:*?"<>|]', '_'
    }
    $dest = Join-Path $Root (Join-Path 'local_backups\vpp_inputs' (Join-Path $timestamp $relative))
    New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
    Copy-Item -LiteralPath $Path -Destination $dest -Force
}

function New-InputNode {
    param(
        [xml]$Xml,
        [string]$Name,
        [string]$Key
    )
    $input = $Xml.CreateElement('input')
    $input.SetAttribute('name', $Name)
    $button = $Xml.CreateElement('btn')
    $button.SetAttribute('name', $Key)
    [void]$input.AppendChild($button)
    return $input
}

function Remove-Inputs {
    param(
        [xml]$Xml,
        [string[]]$Prefixes,
        [string[]]$Names
    )
    $removed = 0
    $nodes = @($Xml.preset.input)
    foreach ($node in $nodes) {
        $name = [string]$node.name
        $matchesPrefix = $false
        foreach ($prefix in $Prefixes) {
            if ($name.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                $matchesPrefix = $true
                break
            }
        }
        if ($matchesPrefix -or ($name -in $Names)) {
            [void]$node.ParentNode.RemoveChild($node)
            $removed++
        }
    }
    return $removed
}

function Ensure-Hotkey {
    param(
        [xml]$Xml,
        [string]$Name,
        [string]$Key
    )
    $existing = @($Xml.preset.input | Where-Object { $_.name -eq $Name })
    foreach ($node in $existing) {
        [void]$node.ParentNode.RemoveChild($node)
    }

    $newNode = New-InputNode -Xml $Xml -Name $Name -Key $Key
    $firstController = @($Xml.preset.controller | Select-Object -First 1)[0]
    if ($firstController) {
        [void]$Xml.preset.InsertBefore($newNode, $firstController)
    } else {
        [void]$Xml.preset.AppendChild($newNode)
    }
}

function Repair-Preset {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    [xml]$xml = Get-Content -LiteralPath $Path -Raw
    if (-not $xml.preset) { return $null }

    $before = Get-Content -LiteralPath $Path -Raw
    $removed = Remove-Inputs -Xml $xml -Prefixes @('UACOT') -Names @(
        'UATeleportModuleTeleportCursor',
        'UATeleportModuleWorldToModelLookAt',
        'UACameraToolToggleCamera',
        'UACameraToolZoomForwards',
        'UACameraToolZoomBackwards',
        'UACameraToolSpeedIncrease',
        'UACameraToolSpeedDecrease',
        'UAObjectModuleDeleteOnCursor',
        'UAObjectModuleSpawnInfected',
        'UAObjectModuleSpawnAnimal',
        'UAObjectModuleSpawnWolf',
        'UAPlayerModuleFreezePlayer',
        'UAPlayerModuleHeal',
        'UAPlayerModuleGodMode',
        'UAPlayerModuleInvisibility',
        'UAPlayerModuleCanBeTargetedByAI',
        'UAPlayerModuleUnlimitedStamina',
        'UAPlayerModuleUnlimitedAmmo',
        'UAPlayerModuleAdminNV',
        'UAPlayerModuleStopSpectating'
    )
    Ensure-Hotkey -Xml $xml -Name 'UAToggleAdminTools' -Key 'kEnd'
    Ensure-Hotkey -Xml $xml -Name 'UAOpenAdminTools' -Key 'kHome'

    $settings = New-Object System.Xml.XmlWriterSettings
    $settings.Indent = $true
    $settings.Encoding = New-Object System.Text.UTF8Encoding($false)
    $builder = New-Object System.Text.StringBuilder
    $writer = [System.Xml.XmlWriter]::Create($builder, $settings)
    $xml.Save($writer)
    $writer.Close()
    $after = $builder.ToString()

    if ($before -ne $after) {
        Backup-File -Path $Path
        try {
            [System.IO.File]::WriteAllText($Path, $after, $settings.Encoding)
        } catch [System.UnauthorizedAccessException] {
            $item = Get-Item -LiteralPath $Path -ErrorAction Stop
            if ($item.Attributes -band [System.IO.FileAttributes]::ReadOnly) {
                $item.Attributes = $item.Attributes -bxor [System.IO.FileAttributes]::ReadOnly
                [System.IO.File]::WriteAllText($Path, $after, $settings.Encoding)
            } else {
                return "skipped access-denied"
            }
        }
        return "updated removed=$removed"
    }
    return "ok removed=$removed"
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

$targets = New-Object System.Collections.Generic.List[string]
foreach ($entry in $maps) {
    $targets.Add((Join-Path $Root (Join-Path $entry.Value.profiles_dir 'Users\Survivor\Server.dayz_preset_User.xml')))
}
$targets.Add((Join-Path $Root 'Server.dayz_preset_User.xml'))
$targets.Add((Join-Path $Root 'config\Users\Survivor\Server.dayz_preset_User.xml'))

if ($IncludeClientProfiles) {
    $targets.Add((Join-Path $env:USERPROFILE 'Documents\DayZ\Owenl.dayz_preset_User.xml'))
    $targets.Add((Join-Path $env:USERPROFILE 'Documents\DayZ\Owenl.preset_X1MouseKey.xml'))
    $targets.Add((Join-Path $env:USERPROFILE 'OneDrive\Documents\DayZ\Owenl.dayz_preset_User.xml'))
    $targets.Add((Join-Path $env:USERPROFILE 'OneDrive\Documents\DayZ\Owenl.preset_X1MouseKey.xml'))
}

Write-Host "VPP input repair"
foreach ($path in ($targets | Select-Object -Unique)) {
    $status = Repair-Preset -Path $path
    if ($status) {
        Write-Host "  $status`t$path"
    }
}
Write-Host "Restart DayZ/server clients after repairing input presets."
